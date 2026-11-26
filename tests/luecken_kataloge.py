"""Attrappe der Kataloge für die Lücken (BF-75): Antworten in der Form der Mitschnitte der Nationalbibliothek und des
Verbundkatalogs (SRU, MARC 21), aber mit erfundenen Reihen, Titeln, Namen und ISBN. Nur die Felder, die die App liest."""

from __future__ import annotations

from xml.sax.saxutils import escape

SPRACHEN = {"de": "ger", "en": "eng", "fr": "fre"}


def _feld(tag: str, *teile: tuple[str, str], ind1: str = " ", ind2: str = " ") -> str:
    unter = "".join(f'<m:subfield code="{c}">{escape(w)}</m:subfield>' for c, w in teile if w)
    return f'<m:datafield tag="{tag}" ind1="{ind1}" ind2="{ind2}">{unter}</m:datafield>'


def satz(titel: str, reihe: str = "", band: str = "", *, feld: str = "490", teil: str = "", teiltitel: str = "",
         autor: str = "Sandvoss, Henrike", isbn: str = "", jahr: int = 2020, sprache: str = "de") -> str:
    """Ein Band: die Reihe in `feld` (490 oder 830) mit Band in $v, oder als mehrbändiges Werk mit `teil` in 245 $n."""
    code = SPRACHEN.get(sprache, sprache)
    felder = [
        '<m:leader>00000nam a2200000 c 4500</m:leader>',
        f'<m:controlfield tag="008">200101s{jahr}    gw ||||| |||| 00||||{code}  </m:controlfield>',
        _feld("020", ("a", isbn)) if isbn else "",
        _feld("041", ("a", code)),
        _feld("100", ("a", autor), ("4", "aut"), ind1="1"),
        _feld("245", ("a", titel), ("n", teil), ("p", teiltitel), ind1="1", ind2="0"),
        _feld("264", ("b", "Verlag am Deich"), ("c", str(jahr)), ind2="1"),
        _feld(feld, ("a", reihe), ("v", band), ind1="1" if feld == "490" else " ", ind2="0" if feld == "830" else " ") if reihe else "",
    ]
    return f'<record><recordData><m:record type="Bibliographic">{"".join(felder)}</m:record></recordData></record>'


def antwort_mit(*saetze: str) -> bytes:
    return ('<?xml version="1.0" encoding="utf-8"?><searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/" '
            'xmlns:m="http://www.loc.gov/MARC21/slim"><version>1.1</version>'
            f'<numberOfRecords>{len(saetze)}</numberOfRecords><records>{"".join(saetze)}</records></searchRetrieveResponse>').encode()
