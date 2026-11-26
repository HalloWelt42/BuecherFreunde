"""Was eine Bandnummer bedeutet (BF-75), für die Bücher einer Sammlung (`books.band_nummer`) wie für die Kataloge ("Bd. 3").

- Eine ganze Zahl ("3", "03", "Band 3", "Bd. 3", "3.", "[3]") belegt ihren Platz der Zählung.
- Ein Doppelband ("1-2", "1/2", "1+2") belegt alle Plätze von bis.
- Ein Zwischenband ("3.5", "3,5", "3a") steht hinter seinem Band und belegt keinen Platz: er füllt keine Lücke, und fehlt er,
  ist das keine Lücke. "3.0" ist Band 3.
- Band 0 steht vor Band 1 und belegt keinen Platz, die Zählung beginnt bei 1.
- Ohne Zahl ("Sonderband") steht ein Buch hinter allen Nummern, ohne Band ganz am Ende, wie in der Bandfolge der Liste."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from backend.app.models.grenzen import REIHE_BAENDE_BIS

_WORT = r"(?:band|bd|teil|tl|folge|buch|vol|volume|book|nr|no|nummer|tome|tomo|#)\.?"
_VORN = re.compile(rf"^{_WORT}\s*", re.IGNORECASE)
_HINTEN = re.compile(rf"^(\d+)\.?\s+{_WORT}$", re.IGNORECASE)            # "3. Band"
_GANZ = re.compile(r"^(\d+)\.?$")
_DOPPEL = re.compile(r"^(\d+)\s*(?:-|/|\+|&|\u2013|bis)\s*(\d+)$", re.IGNORECASE)
_DEZIMAL = re.compile(r"^(\d+)[.,](\d+)$")
_BUCHSTABE = re.compile(r"^(\d+)\s*([a-z])$", re.IGNORECASE)
DOPPEL_HOECHSTENS = 20                       # weiter auseinander ist es kein Doppelband, sondern etwas anderes


class Bandnummer(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str                                # wie es dasteht
    von: int | None = None                   # die Zahl; leer: keine
    bis: int | None = None                   # beim Doppelband die letzte, sonst wie von
    zusatz: str = ""                         # beim Zwischenband: "5" aus "3.5", "a" aus "3a"
    dezimal: bool = False                    # der Zusatz ist ein Teil nach dem Komma

    @property
    def zwischen(self) -> bool:
        return bool(self.zusatz)

    @property
    def plaetze(self) -> range:
        """Die Plätze der Zählung, die dieser Band belegt."""
        if self.von is None or self.bis is None or self.zusatz:
            return range(0)
        return range(max(self.von, 1), min(self.bis, REIHE_BAENDE_BIS) + 1)

    @property
    def ordnung(self) -> tuple:
        """Zum Sortieren: Nummern der Zahl nach, Zwischenbände hinter ihrem Band, ohne Zahl dahinter, ohne Band zuletzt."""
        if self.von is None:
            return (1 if self.text else 2, 0, (0, 0.0, ""), self.text.casefold())
        rest = (0, 0.0, "") if not self.zusatz else (1, float(f"0.{self.zusatz}"), "") if self.dezimal else (2, 0.0, self.zusatz.casefold())
        return (0, self.von, rest, self.text.casefold())


def _ohne_rand(text: str) -> str:
    t = text.strip().strip("[]()").strip()
    return _VORN.sub("", t).strip()


def lesen(text: str | None) -> Bandnummer:
    roh = (text or "").strip()
    t = _ohne_rand(roh)
    if m := _HINTEN.match(t) or _GANZ.match(t):
        n = int(m[1])
        return Bandnummer(text=roh, von=n, bis=n)
    if (m := _DOPPEL.match(t)) and 0 < int(m[2]) - int(m[1]) <= DOPPEL_HOECHSTENS:
        return Bandnummer(text=roh, von=int(m[1]), bis=int(m[2]))
    if m := _DEZIMAL.match(t):
        n, teil = int(m[1]), m[2].rstrip("0")
        return Bandnummer(text=roh, von=n, bis=n, zusatz=teil, dezimal=True) if teil else Bandnummer(text=roh, von=n, bis=n)
    if m := _BUCHSTABE.match(t):
        n = int(m[1])
        return Bandnummer(text=roh, von=n, bis=n, zusatz=m[2].lower())
    return Bandnummer(text=roh)


def platz(nummer: int) -> Bandnummer:
    """Der Band an einem Platz der Zählung, etwa für eine Lücke."""
    return Bandnummer(text=str(nummer), von=nummer, bis=nummer)
