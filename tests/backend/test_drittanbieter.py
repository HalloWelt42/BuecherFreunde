"""Pakete des Servers für die Seite Drittanbieter (BF-90): aus den installierten Metadaten, mit dem Weg über requirements.txt."""

from email.message import Message

from backend.app.drittanbieter import pakete as p


def _angaben(**felder: str | list[str]) -> Message:
    """Metadaten wie in METADATA; Unterstrich im Namen steht für den Bindestrich, eine Liste für mehrere Zeilen."""
    m = Message()
    for name, wert in felder.items():
        for w in wert if isinstance(wert, list) else [wert]:
            m[name.replace("_", "-")] = w
    return m


def test_anforderung_liest_requirements_und_requires_dist():
    assert p.anforderung("fastapi==0.115.6") == p.Anforderung(name="fastapi")
    assert p.anforderung("uvicorn[standard]==0.34.0") == p.Anforderung(name="uvicorn", extras=frozenset({"standard"}))
    assert p.anforderung("requests>=2.31.0                # Abruf der Quellen").name == "requests"
    assert p.anforderung("beispiel[web] @ https://example.org/archiv/abc.tar.gz") == p.Anforderung(name="beispiel", extras=frozenset({"web"}))
    assert p.anforderung('httptools>=0.6.3; extra == "standard"') == p.Anforderung(name="httptools", nur_mit="standard")
    assert p.anforderung("Typing_Extensions>=4.0; python_version < '3.11'") == p.Anforderung(name="typing-extensions")
    for keine in ("", "   ", "# nur ein Kommentar", "-r weitere.txt", "--index-url https://example.org/simple"):
        assert p.anforderung(keine) is None


def test_ueber_folgt_den_wurzeln_und_nur_verlangten_extras():
    a = p.Anforderung
    verlangt = {
        "a": [a(name="c")],
        "b": [a(name="d", nur_mit="x"), a(name="e", nur_mit="y"), a(name="fehlt")],
        "c": [a(name="d"), a(name="a")],                     # Kreis zurück zur Wurzel
        "d": [],
        "e": [],
        "f": [],                                             # installiert, aber von keiner Wurzel verlangt
    }
    erreicht = p.ueber_aus([a(name="a"), a(name="b", extras=frozenset({"x"})), a(name="nicht-installiert")], verlangt)
    assert erreicht == {"a": {"a"}, "b": {"b"}, "c": {"a"}, "d": {"a", "b"}}


def test_lizenz_wie_das_paket_sie_angibt():
    assert p.lizenz_aus(_angaben(License_Expression="MIT OR Apache-2.0", License="MIT")) == "MIT OR Apache-2.0"
    assert p.lizenz_aus(_angaben(License="BSD-3-Clause", Classifier="License :: OSI Approved :: MIT License")) == "BSD-3-Clause"
    lang = "Copyright (c) Jemand\n\nPermission is hereby granted, free of charge, ..."
    klassen = ["License :: OSI Approved", "License :: OSI Approved :: MIT License", "Programming Language :: Python"]
    assert p.lizenz_aus(_angaben(License=lang, Classifier=klassen)) == "MIT License"
    assert p.lizenz_aus(_angaben(License="UNKNOWN")) == ""
    text = "Eigene Lizenz\n\nSPDX-License-Identifier: LicenseRef-Beispiel-1.0\n"
    assert p.lizenz_aus(_angaben(), [text]) == "LicenseRef-Beispiel-1.0"
    assert p.lizenz_aus(_angaben(), ["ohne Kennung"]) == ""


def test_lizenztexte_nur_gelesen_wenn_noetig():
    def nie():
        raise AssertionError("gelesen, obwohl das Paket seine Lizenz nennt")
        yield ""

    assert p.lizenz_aus(_angaben(License_Expression="MIT"), nie()) == "MIT"


def test_adresse_startseite_sonst_quelle():
    assert p.adresse_aus(_angaben(Home_page="https://example.org/paket")) == "https://example.org/paket"
    urls = ["Documentation, https://docs.example.org", "Source Code, https://example.org/quelle", "Chat, irc://example.org"]
    assert p.adresse_aus(_angaben(Project_URL=urls)) == "https://example.org/quelle"
    assert p.adresse_aus(_angaben(Project_URL="Documentation, https://docs.example.org")) == "https://docs.example.org"
    assert p.adresse_aus(_angaben(Home_page="UNKNOWN")) == ""


def test_requirements_txt_ist_die_wurzel():
    namen = {a.name for a in p.wurzeln()}
    assert {"fastapi", "uvicorn", "requests", "appkern"} <= namen
    assert next(a for a in p.wurzeln() if a.name == "uvicorn").extras == frozenset({"standard"})


def test_pakete_dieser_umgebung():
    liste = p.pakete()
    namen = [x.name for x in liste]
    assert namen == sorted(namen, key=str.casefold)
    fastapi = next(x for x in liste if x.name == "fastapi")
    assert fastapi.ueber == ["fastapi"] and fastapi.fassung and fastapi.lizenz
    starlette = next(x for x in liste if x.name == "starlette")
    assert "fastapi" in starlette.ueber
    installiert = {p.normiert(x.name): x for x in liste}
    for wurzel in p.wurzeln():
        if wurzel.name in installiert:
            assert installiert[wurzel.name].ueber == [installiert[wurzel.name].name]
