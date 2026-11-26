"""Code ausführen und aufzeichnen (BF-29): BücherFreunde rechnet nichts selbst. Es schickt Code und Sprache an die Sandbox
der Codeschmiede (`CODESCHMIEDE_URL`), mit seinem App-Zugang der Kellerwolke; die Codeschmiede nimmt nur Apps auf ihrer
Erlaubnisliste an und lässt den Code ohne Netz, nur lesend und mit Grenzen laufen. Was sie kann, sagt sie selbst (Sprachen,
bei PHP die Fassungen, ob aufgezeichnet wird); das Angebot gilt zehn Minuten.

Die Codeschmiede nimmt je App nur einen Lauf zugleich an. Darum reiht dieser Anschluss die eigenen Läufe ein, Menschen vor
der Vorprüfung im Hintergrund. Geht es nicht, kommt ein Grund statt eines Fehlers."""

from __future__ import annotations

import asyncio
import heapq
import itertools
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.app.services.hausdienst import DienstFehler, Hausdienst

Sprache = Literal["python", "javascript", "php"]
SPRACHEN: tuple[str, ...] = ("python", "javascript", "php")
ANGEBOT_GILT_S = 600
HOECHSTENS_ZEICHEN = 20_000
LAUF_S = 120.0                            # Antwortzeit eines Laufs (die Sandbox selbst bricht nach ihren Grenzen ab)

KEINE_ADRESSE = "Keine Codeschmiede eingetragen (CODESCHMIEDE_URL)"
NICHT_ERREICHBAR = "Sandbox gerade nicht erreichbar"
NICHT_ZUGELASSEN = "Diese App darf die Sandbox nicht nutzen"
BESETZT = "Die Sandbox rechnet gerade für BücherFreunde; gleich noch einmal"


class Sprachangebot(BaseModel):
    sprache: str
    fassungen: list[str] = Field(default_factory=list)    # neueste zuerst; leer: eine Fassung
    aufzeichnen: bool = False                             # ob der Debugger den Lauf aufzeichnet (sonst nur ausführen)


class Ausfuehrstand(BaseModel):
    bereit: bool
    sprachen: list[Sprachangebot] = Field(default_factory=list)
    grund: str = ""


class Aufzeichnung(BaseModel):
    """Der Lauf, wie die Codeschmiede ihn liefert: Ausgabe, Fehler mit Zeile, Hinweise und je Schritt Zeile, Aufrufe mit
    ihren Variablen, Ausgabe und Rückgabe (Form der Codeschmiede, für den Debugger der Oberfläche unverändert). Ohne
    Aufzeichnung sind die Schritte leer."""

    model_config = ConfigDict(extra="ignore")

    art: str = ""
    ausgabe: str = ""
    fehler: str | None = None
    fehlerzeile: int | None = None
    hinweise: str = ""
    gekuerzt: bool = False
    zeitueberschreitung: bool = False
    laufzeit_ms: float = 0
    schritte: list[dict[str, Any]] = Field(default_factory=list)


class Lauf(BaseModel):
    aufzeichnung: Aufzeichnung | None = None
    grund: str = ""                                       # warum es gerade nicht ging; dann ohne Aufzeichnung


class SandboxFehler(Exception):
    """Für Läufe im Hintergrund: `art` sagt, ob es gleich wieder gehen kann (weg, besetzt) oder ein Mensch gefragt ist
    (abgelehnt, ungeeignet)."""

    def __init__(self, grund: str, art: Literal["weg", "abgelehnt", "besetzt", "ungeeignet"]) -> None:
        super().__init__(grund)
        self.grund, self.art = grund, art


def grund(f: DienstFehler) -> str:
    if f.antwort is None:
        return NICHT_ERREICHBAR if "nicht angeschlossen" not in f.meldung else KEINE_ADRESSE
    if f.antwort in (401, 403):
        return NICHT_ZUGELASSEN
    if f.antwort == 429:
        return BESETZT
    return f.meldung


def _art(f: DienstFehler) -> Literal["weg", "abgelehnt", "besetzt", "ungeeignet"]:
    if f.antwort is None or f.antwort >= 500:
        return "weg"
    if f.antwort in (401, 403):
        return "abgelehnt"
    return "besetzt" if f.antwort == 429 else "ungeeignet"


def mit_php_marke(code: str, sprache: str) -> str:
    """PHP aus Büchern steht oft ohne `<?php`; ohne die Marke gäbe PHP den Text nur aus. Sie kommt vor die erste Zeile,
    damit die Zeilennummern des Laufs zu denen im Buch passen."""
    if sprache == "php" and "<?php" not in code and "<?=" not in code:
        return "<?php " + code
    return code


class Reihe:
    """Ein Lauf nach dem anderen; wer vorne steht (Menschen), kommt vor der Vorprüfung im Hintergrund dran."""

    def __init__(self) -> None:
        self._wartend: list[tuple[int, int, asyncio.Future[None]]] = []
        self._zaehler = itertools.count()
        self._belegt = False

    @property
    def wartend(self) -> int:
        return len(self._wartend)

    @asynccontextmanager
    async def platz(self, vorrang: bool) -> AsyncIterator[None]:
        if self._belegt or self._wartend:
            dran: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            heapq.heappush(self._wartend, (0 if vorrang else 1, next(self._zaehler), dran))
            try:
                await dran
            except asyncio.CancelledError:
                if dran.done() and not dran.cancelled():
                    self._weiter()                         # war schon dran: den Platz weitergeben
                else:
                    self._wartend = [w for w in self._wartend if w[2] is not dran]
                    heapq.heapify(self._wartend)
                raise
        self._belegt = True
        try:
            yield
        finally:
            self._weiter()

    def _weiter(self) -> None:
        while self._wartend:
            _, _, dran = heapq.heappop(self._wartend)
            if not dran.done():
                dran.set_result(None)
                return
        self._belegt = False


class Sandbox:
    def __init__(self) -> None:
        self.dienst = Hausdienst("Codeschmiede", lambda: settings.codeschmiede_url, zeit_s=LAUF_S)
        self.reihe = Reihe()
        self._angebot: tuple[float, str, list[Sprachangebot]] | None = None     # (geholt, Adresse, Angebot)
        self._funktionen: dict[str, list[str]] = {}

    @property
    def angeschlossen(self) -> bool:
        return bool(settings.codeschmiede_url.strip())

    async def schliessen(self) -> None:
        await self.dienst.schliessen()

    async def angebot(self) -> list[Sprachangebot]:
        """Was die Sandbox kann; wirft DienstFehler, wenn sie nicht antwortet."""
        adresse = self.dienst.adresse
        if self._angebot and self._angebot[1] == adresse and time.monotonic() - self._angebot[0] < ANGEBOT_GILT_S:
            return self._angebot[2]
        antwort = await self.dienst.hole("GET", "/api/v1/sandbox/sprachen", timeout=10.0)
        angebot = [Sprachangebot.model_validate(s) for s in antwort.json() if s.get("sprache") in SPRACHEN]
        self._angebot = (time.monotonic(), adresse, angebot)
        return angebot

    async def sprachen(self) -> set[str]:
        """Die Sprachen der Sandbox, soweit sie gerade bekannt sind (leer ohne Codeschmiede oder ohne Antwort)."""
        if not self.angeschlossen:
            return set()
        try:
            return {s.sprache for s in await self.angebot()}
        except DienstFehler:
            return set()

    async def stand(self) -> Ausfuehrstand:
        if not self.angeschlossen:
            return Ausfuehrstand(bereit=False, grund=KEINE_ADRESSE)
        try:
            return Ausfuehrstand(bereit=True, sprachen=await self.angebot())
        except DienstFehler as f:
            return Ausfuehrstand(bereit=False, grund=grund(f))

    async def laufen(self, code: str, sprache: str, fassung: str = "", eingabe: list[str] | None = None) -> Lauf:
        """Ein Lauf für einen Menschen: mit Aufzeichnung, wo die Sprache sie hat, sonst nur ausführen."""
        if not self.angeschlossen:
            return Lauf(grund=KEINE_ADRESSE)
        try:
            angebot = {s.sprache: s for s in await self.angebot()}
            if sprache not in angebot:
                return Lauf(grund=f"Die Sandbox kann {sprache} nicht ausführen")
            koerper: dict[str, Any] = {"code": mit_php_marke(code, sprache), "sprache": sprache}
            if fassung:
                koerper["fassung"] = fassung
            async with self.reihe.platz(vorrang=True):
                if angebot[sprache].aufzeichnen:
                    antwort = await self.dienst.hole("POST", "/api/v1/sandbox/aufzeichnen", json={**koerper, "eingabe": eingabe or []})
                    return Lauf(aufzeichnung=Aufzeichnung.model_validate(antwort.json()))
                antwort = await self.dienst.hole("POST", "/api/v1/sandbox/ausfuehren", json=koerper)
                return Lauf(aufzeichnung=Aufzeichnung.model_validate({**antwort.json(), "schritte": []}))
        except DienstFehler as f:
            return Lauf(grund=grund(f))

    async def pruefen(self, code: str, sprache: str) -> Aufzeichnung:
        """Ein Lauf im Hintergrund (Vorprüfung): nur ausführen, hinter allen Menschen. Wirft SandboxFehler."""
        if not self.angeschlossen:
            raise SandboxFehler(KEINE_ADRESSE, "abgelehnt")
        try:
            async with self.reihe.platz(vorrang=False):
                antwort = await self.dienst.hole("POST", "/api/v1/sandbox/ausfuehren",
                                                 json={"code": mit_php_marke(code, sprache), "sprache": sprache})
            return Aufzeichnung.model_validate(antwort.json())
        except DienstFehler as f:
            raise SandboxFehler(grund(f), _art(f)) from f

    async def funktionen_php(self) -> dict[str, list[str]]:
        """Je PHP-Fassung die eingebauten Funktionen (für den Editor); gemerkt, sobald alle Fassungen geantwortet haben.
        Leer, wenn die Codeschmiede nicht antwortet: dann prüft der Editor nur die Schreibweise."""
        if not self.angeschlossen:
            return {}
        try:
            angebot = {s.sprache: s for s in await self.angebot()}
            fassungen = angebot["php"].fassungen if "php" in angebot else []
            if not (fassungen and all(f in self._funktionen for f in fassungen)):
                self._funktionen.update((await self.dienst.hole("GET", "/api/v1/sandbox/funktionen/php")).json())
            return {f: self._funktionen[f] for f in fassungen if f in self._funktionen}
        except DienstFehler:
            return {}


sandbox = Sandbox()
