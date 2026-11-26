"""Ein Original zum Übersetzen (BF-71): EPUB und PDF hinter einer Schnittstelle. Zerlegt wird immer ein EPUB, beim PDF das
englische, das der Aufbau daraus baut (zerlegen_pdf.py); gesetzt wird daraus die deutsche Fassung als EPUB (setzen.py).
Was danach kommt (Begriffe, Übersetzen, Prüfkette, Lauf, Bericht), kennt das Format nicht. Die Blöcke eines PDF tragen ihre
Seite und Lage im Original."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.app.uebersetzung import zerlegen_pdf
from backend.app.uebersetzung.modelle import Block
from backend.app.uebersetzung.setzen import Satz, setzen
from backend.app.uebersetzung.zerlegen_epub import Dokument, NichtLesbar, Zerlegung
from backend.app.uebersetzung.zerlegen_epub import zerlegen as epub_zerlegen
from backend.app.uebersetzung.zerlegen_pdf import Seitenlage

#: Formate, die übersetzt werden, und womit sie zerlegt werden (ändert es sich, wird neu zerlegt)
FORMATE: dict[str, str] = {"epub": "", "pdf": f"pdf{zerlegen_pdf.FASSUNG}"}

__all__ = ["FORMATE", "NichtLesbar", "Werk", "zerlegen"]


@dataclass(eq=False)
class Werk:
    format: str
    epub: bytes                                      # woraus gesetzt wird: das Original, beim PDF das EPUB aus dem Aufbau
    zerlegung: Zerlegung
    sprache: str = ""                                # laut Datei; leer: unbekannt
    seiten: int | None = None                        # Seiten des PDF
    lagen: dict[str, Seitenlage] = field(default_factory=dict)
    nicht_lesbar: list[str] = field(default_factory=list)

    def bloecke(self) -> list[Block]:
        aus = []
        for b in self.zerlegung.bloecke():
            lage = self.lagen.get(b.kennung)
            aus.append(b if lage is None else b.model_copy(update={"seite": lage.seite, "gedruckt": lage.gedruckt, "lage": lage.lage}))
        return aus

    def kapitel(self) -> list[Dokument]:
        """Die Kapitel mit Blöcken (bei EPUB und PDF auch das Inhaltsverzeichnis)."""
        return self.zerlegung.mit_bloecken()

    @property
    def abbildungen(self) -> int:
        return self.zerlegung.abbildungen

    def setzen(self, satz: Satz) -> bytes:
        """Die deutsche Fassung als EPUB; beim PDF sagt das Blatt "Über diese Übersetzung", was die Seitenmarken zeigen."""
        if self.format == "pdf" and satz.hinweis is not None:
            satz = satz.model_copy(update={"hinweis": satz.hinweis.model_copy(update={"seitenmarken": True})})
        return setzen(self.epub, self.zerlegung, satz)


def zerlegen(daten: bytes, format: str, nie_klassen: frozenset[str] = frozenset(), gedruckt: Sequence[str] = (), titel: str = "",
             autor: str = "") -> Werk:
    """Das Original in Blöcke; `gedruckt` (die Beschriftungen der Seiten), `titel` und `autor` gelten nur für PDF. Wirft
    NichtLesbar mit einem deutschen Satz, wenn es nicht geht (beim Scan: zerlegen_pdf.OhneText)."""
    art = format.lower().lstrip(".")
    if art == "pdf":
        z = zerlegen_pdf.zerlegen(daten, nie_klassen, gedruckt, titel, autor)
        return Werk("pdf", z.epub, z.zerlegung, sprache=z.sprache, seiten=z.seiten, lagen=z.lagen,
                    nicht_lesbar=z.nicht_lesbar + z.zerlegung.nicht_lesbar)
    if art == "epub":
        z = epub_zerlegen(daten, nie_klassen)
        return Werk("epub", daten, z, sprache=z.sprache, nicht_lesbar=z.nicht_lesbar)
    raise NichtLesbar(f"Das Format {art.upper() or 'ohne Endung'} wird nicht übersetzt")
