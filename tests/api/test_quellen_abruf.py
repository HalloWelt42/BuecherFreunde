"""Der gemeinsame Abruf der Quellen: Vorrat, Zusammenfassen, Takt, Rückzug, Sicherung, Tagesgrenze (BF-23)."""

import asyncio
import os
import time

import pytest

from backend.app.core.config import settings
from backend.app.quellen import stand
from backend.app.quellen import abruf as quellen_abruf
from backend.app.quellen.abruf import Abruf, Frage, wartezeit
from backend.app.quellen.fehler import Abgeschaltet, AnfrageFalsch, Ausgefallen, Pausiert, Tagesgrenze
from backend.app.quellen.regeln import CROSSREF, DNB, GOOGLE_BOOKS, OPEN_LIBRARY, REGELN, WIKIPEDIA
from backend.app.quellen.takt import Takt
from backend.app.quellen.versand import ausweis
from backend.app.quellen.vorrang import Vorrang, hintergrund
from backend.app.quellen.zustand import SICHERUNG_AB, SICHERUNG_S
from tests.quellen_netz import AUSFALL, Netz, Uhr, abruf_mit, antwort, ohne_takt

RECHNER = "services.dnb.de"
FRAGE = Frage("https://services.dnb.de/sru/dnb", (("query", "NUM=1"),), ist_leer=lambda w: not w)


@pytest.fixture
def uhr():
    return Uhr()


@pytest.fixture
def abruf(test_db, uhr):
    """Abruf mit Netz aus Mitschnitten und einer Uhr, die der Test stellt."""
    netz = Netz()
    a = abruf_mit(netz, uhr)
    a.netz = netz
    return a


# -- Vorrat ------------------------------------------------------------------------------------------------------------
async def test_dieselbe_frage_geht_nur_einmal_hinaus_und_gilt_lange(abruf, uhr):
    abruf.netz.setze(RECHNER, antwort({"titel": "Grundstein"}))
    assert await abruf.hole(DNB, FRAGE) == {"titel": "Grundstein"}
    uhr.zeit += 80 * 24 * 3600
    assert await abruf.hole(DNB, FRAGE) == {"titel": "Grundstein"}
    assert abruf.netz.zahl() == 1
    uhr.zeit += 20 * 24 * 3600
    await abruf.hole(DNB, FRAGE)
    assert abruf.netz.zahl() == 2, "nach der Frist wird neu gefragt"


async def test_leere_antworten_gelten_kuerzer_fehler_ganz_kurz(abruf, uhr):
    abruf.netz.setze(RECHNER, antwort([]), AUSFALL, antwort(["da"]))
    assert await abruf.hole(DNB, FRAGE) is None
    uhr.zeit += 13 * 24 * 3600
    assert await abruf.hole(DNB, FRAGE) is None and abruf.netz.zahl() == 1
    uhr.zeit += 2 * 24 * 3600
    for _ in range(3):
        with pytest.raises(Ausgefallen, match="Verzeichnis 3: antwortet nicht"):
            await abruf.hole(DNB, FRAGE)
    assert abruf.netz.zahl() == 2, "der Fehler ist kurz gemerkt"
    uhr.zeit += DNB.fehler_s + 1
    assert await abruf.hole(DNB, FRAGE) == ["da"]


async def test_reihenfolge_der_felder_und_beiwerk_machen_keine_neue_frage(abruf):
    abruf.netz.setze(RECHNER, antwort({"n": 1}))
    a = Frage(FRAGE.adresse, (("a", "1"), ("b", "2")), beiwerk=(("maxlag", "5"),), kopf=(("X-Goog-Api-Key", "geheim"),))
    b = Frage(FRAGE.adresse, (("b", "2"), ("a", "1")))
    await abruf.hole(DNB, a)
    await abruf.hole(DNB, b)
    assert abruf.netz.zahl() == 1 and "geheim" not in a.schluessel


async def test_vorrat_hat_eine_obergrenze_das_aelteste_geht_zuerst(abruf, uhr, monkeypatch):
    monkeypatch.setattr(settings, "quellen_vorrat_mb", 1)
    for n in range(4):
        uhr.zeit += 1
        await abruf.vorrat.merke(f"https://x/{n}", "dnb", "treffer", 1000, os.urandom(400_000))
    assert await abruf.vorrat.aufraeumen() == 2
    assert [await abruf.vorrat.lies(f"https://x/{n}") is not None for n in range(4)] == [False, False, True, True]
    uhr.zeit += 2000
    assert await abruf.vorrat.aufraeumen() == 2 and await abruf.vorrat.zahlen() == {}, "Abgelaufenes geht"


async def test_statusmeldung_404_heisst_leer_und_anfragefehler_zaehlt_nicht_als_ausfall(abruf):
    abruf.netz.setze(RECHNER, antwort(status=404))
    assert await abruf.hole(DNB, FRAGE) is None
    abruf.netz.setze(RECHNER, antwort(status=400))
    with pytest.raises(AnfrageFalsch):
        await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", "krumm"),)))
    assert (await abruf.zustaende.von("dnb")).ausfaelle == 0


async def test_nur_rechner_der_quelle(abruf):
    for adresse in ("https://anderswo.example/x", "http://services.dnb.de/sru"):
        with pytest.raises(AnfrageFalsch):
            await abruf.hole(DNB, Frage(adresse))
        with pytest.raises(AnfrageFalsch):
            await abruf.lade(DNB, adresse, 1000)
    assert abruf.netz.zahl() == 0


# -- Zusammenfassen ----------------------------------------------------------------------------------------------------
async def test_gleiche_laufende_anfragen_werden_eine(abruf):
    tor = asyncio.Event()

    async def langsam(_a):
        abruf.netz.anfragen.append(_a)
        await tor.wait()
        return antwort({"n": 1})

    abruf._senden = langsam
    laeufe = [asyncio.create_task(abruf.hole(DNB, FRAGE)) for _ in range(5)]
    await asyncio.sleep(0.02)
    tor.set()
    assert await asyncio.gather(*laeufe) == [{"n": 1}] * 5 and abruf.netz.zahl() == 1


async def test_wer_abbricht_nimmt_den_uebrigen_die_antwort_nicht(abruf):
    tor = asyncio.Event()

    async def langsam(_a):
        await tor.wait()
        return antwort({"n": 1})

    abruf._senden = langsam
    einer, anderer = (asyncio.create_task(abruf.hole(DNB, FRAGE)) for _ in range(2))
    await asyncio.sleep(0.02)
    einer.cancel()
    tor.set()
    assert await anderer == {"n": 1}
    with pytest.raises(asyncio.CancelledError):
        await einer


# -- Takt --------------------------------------------------------------------------------------------------------------
async def test_takt_haelt_abstand_und_laesst_nur_einen_zugleich():
    t = Takt(lambda: 0.03, lambda: 1000)
    zugleich, hoechstens, zeiten = 0, 0, []

    async def einer():
        nonlocal zugleich, hoechstens
        async with t.an_der_reihe(t.karte(Vorrang.MENSCH)):
            zugleich += 1
            hoechstens = max(hoechstens, zugleich)
            zeiten.append(time.monotonic())
            await asyncio.sleep(0.005)
            zugleich -= 1

    await asyncio.gather(*(einer() for _ in range(5)))
    assert hoechstens == 1 and all(b - a >= 0.03 for a, b in zip(zeiten, zeiten[1:], strict=False))


async def test_mensch_kommt_vor_dem_hintergrund_dran_auch_nachtraeglich():
    t = Takt(lambda: 0.01, lambda: 1000)
    folge = []

    async def einer(name, karte):
        async with t.an_der_reihe(karte):
            folge.append(name)

    karten = [t.karte(Vorrang.HINTERGRUND) for _ in range(3)]
    laeufe = [asyncio.create_task(einer(f"h{n}", k)) for n, k in enumerate(karten)]
    await asyncio.sleep(0)
    laeufe.append(asyncio.create_task(einer("mensch", t.karte(Vorrang.MENSCH))))
    await asyncio.sleep(0)
    await t.vorziehen(karten[2], Vorrang.MENSCH)
    await asyncio.gather(*laeufe)
    assert folge.index("mensch") < folge.index("h1") and folge.index("h2") < folge.index("h1")


async def test_je_minute_und_hintergrund_nur_ein_teil_davon():
    uhr = Uhr(0.0)
    t = Takt(lambda: 0.0, lambda: 10, uhr)
    for _ in range(6):
        async with t.an_der_reihe(t.karte(Vorrang.MENSCH)):
            uhr.zeit += 1
    assert t.wartet(Vorrang.MENSCH) == 0 and t.wartet(Vorrang.HINTERGRUND) == pytest.approx(55, abs=1.1)
    for _ in range(4):
        async with t.an_der_reihe(t.karte(Vorrang.MENSCH)):
            uhr.zeit += 1
    assert t.wartet(Vorrang.MENSCH) > 40
    uhr.zeit += 60
    assert t.wartet(Vorrang.HINTERGRUND) == 0


async def test_abgebrochenes_warten_raeumt_seinen_platz():
    t = Takt(lambda: 0.02, lambda: 1000)
    async with t.an_der_reihe(t.karte(Vorrang.MENSCH)):
        async def einer():
            async with t.an_der_reihe(t.karte(Vorrang.MENSCH)):
                pass
        wartet = asyncio.create_task(einer())
        await asyncio.sleep(0.01)
        wartet.cancel()
        await asyncio.gather(wartet, return_exceptions=True)
    async with asyncio.timeout(1):
        async with t.an_der_reihe(t.karte(Vorrang.HINTERGRUND)):
            pass


async def test_wikis_zaehlen_gemeinsam_andere_je_rechner(abruf):
    assert abruf._takt(WIKIPEDIA, "https://www.wikidata.org/w") is abruf._takt(WIKIPEDIA, "https://de.wikipedia.org/w")
    assert abruf._takt(OPEN_LIBRARY, "https://openlibrary.org/x") is not abruf._takt(DNB, "https://services.dnb.de/x")


# -- Rückzug und Sicherung ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(("wert", "sekunden"), [("120", 120), ("11.000", 11), ("", None), ("Wed, 25 Nov 2026 22:00:30 GMT", 30), ("unsinn", None)])
def test_retry_after_in_allen_formen(wert, sekunden):
    assert wartezeit({"retry-after": wert}, 1795644000.0) == sekunden


async def test_429_haelt_die_verlangte_pause_und_wird_mit_jedem_mal_laenger(abruf, uhr):
    abruf.netz.setze(RECHNER, antwort(status=429, retry_after="90"))
    with pytest.raises(Pausiert, match="macht Pause bis .*: zu viele Anfragen") as f:
        await abruf.hole(DNB, FRAGE)
    assert f.value.bis == uhr.zeit + 90
    with pytest.raises(Pausiert):
        await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", "anderes"),)))
    assert abruf.netz.zahl() == 1, "in der Pause geht nichts hinaus"
    abruf.netz.setze(RECHNER, antwort(status=429))
    pausen = []
    for n in range(4):
        uhr.zeit = (await abruf.zustaende.von("dnb")).pause_bis + 1
        with pytest.raises(Pausiert) as f:
            await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", f"n{n}"),)))
        pausen.append(round(f.value.bis - uhr.zeit))
    assert pausen == [60, 120, 240, 480]
    uhr.zeit = (await abruf.zustaende.von("dnb")).pause_bis + 1
    abruf.netz.setze(RECHNER, antwort({"n": 1}))
    await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", "gut"),)))
    z = await abruf.zustaende.von("dnb")
    assert (z.stufe, z.pause_bis, z.ausfaelle) == (0, None, 0), "ein Erfolg setzt alles zurück"


async def test_503_mit_und_ohne_angabe_und_403(abruf, uhr):
    abruf.netz.setze(RECHNER, antwort(status=503, retry_after="21600"))
    with pytest.raises(Pausiert) as f:
        await abruf.hole(DNB, FRAGE)
    assert f.value.bis - uhr.zeit == 21600
    uhr.zeit += 21601
    abruf.netz.setze(RECHNER, antwort(status=503))
    with pytest.raises(Ausgefallen, match="Fehler 503"):
        await abruf.hole(DNB, FRAGE)
    abruf.netz.setze("api.crossref.org", antwort(status=403))
    with pytest.raises(Pausiert, match="weist die Anfrage ab") as f:
        await abruf.hole(CROSSREF, Frage("https://api.crossref.org/works/x"))
    assert f.value.bis - uhr.zeit == 3600


async def test_sicherung_nach_mehreren_ausfaellen_mit_probe_danach(abruf, uhr):
    abruf.netz.setze(RECHNER, AUSFALL)
    for n in range(SICHERUNG_AB - 1):
        with pytest.raises(Ausgefallen):
            await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", str(n)),)))
    with pytest.raises(Pausiert, match="mehrmals ausgefallen, zuletzt: antwortet nicht rechtzeitig"):
        await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", "viertes"),)))
    with pytest.raises(Pausiert):
        await abruf.hole(DNB, FRAGE)
    assert abruf.netz.zahl() == SICHERUNG_AB
    uhr.zeit += SICHERUNG_S + 1
    with pytest.raises(Pausiert) as f:
        await abruf.hole(DNB, FRAGE)
    assert abruf.netz.zahl() == SICHERUNG_AB + 1 and f.value.bis - uhr.zeit == 2 * SICHERUNG_S, "ein Versuch, dann doppelt so lange"


async def test_unlesbares_zaehlt_als_ausfall(abruf):
    abruf.netz.setze(RECHNER, antwort("<html>kaputt"))
    with pytest.raises(Ausgefallen, match="liefert Unlesbares"):
        await abruf.hole(DNB, FRAGE)
    abruf.netz.setze(RECHNER, antwort({"anders": 1}))
    with pytest.raises(Ausgefallen, match="liefert Unlesbares"):
        await abruf.hole(DNB, Frage(FRAGE.adresse, (("query", "2"),), verdichte=lambda w: w["fehlt"]))
    assert (await abruf.zustaende.von("dnb")).ausfaelle == 2


async def test_stand_und_pause_ueberstehen_einen_neustart(abruf, uhr):
    abruf.netz.setze(RECHNER, antwort(status=429, retry_after="600"))
    with pytest.raises(Pausiert):
        await abruf.hole(DNB, FRAGE)
    neu = Abruf(abruf.netz, uhr, ohne_takt)
    with pytest.raises(Pausiert):
        await neu.hole(DNB, FRAGE)
    assert abruf.netz.zahl() == 1


# -- Tagesgrenze, Schalter, Ausweis ------------------------------------------------------------------------------------
async def test_tagesgrenze_gilt_nur_im_hintergrund_und_endet_um_mitternacht(abruf, uhr, monkeypatch):
    monkeypatch.setattr(settings, "quellen_hintergrund_tag", 2)
    abruf.netz.setze(RECHNER, antwort({"n": 1}))
    fragen = [Frage(FRAGE.adresse, (("query", str(n)),)) for n in range(6)]
    with hintergrund():
        await abruf.hole(DNB, fragen[0])
        await abruf.hole(DNB, fragen[1])
        with pytest.raises(Tagesgrenze, match="für heute genug gefragt"):
            await abruf.hole(DNB, fragen[2])
        await abruf.hole(DNB, fragen[0])
    await abruf.hole(DNB, fragen[2])
    z = await abruf.zustaende.von("dnb")
    assert (z.anfragen, z.hintergrund) == (3, 2)
    uhr.zeit += 24 * 3600
    with hintergrund():
        await abruf.hole(DNB, fragen[3])


async def test_abgeschaltet_oder_ohne_schluessel_geht_nichts_hinaus(abruf, monkeypatch):
    monkeypatch.setattr(settings, "dnb_enabled", False)
    with pytest.raises(Abgeschaltet, match="Verzeichnis 3 ist abgeschaltet"):
        await abruf.hole(DNB, FRAGE)
    monkeypatch.setattr(settings, "google_books_api_key", "")
    with pytest.raises(Abgeschaltet, match="nur mit eigenem Schlüssel"):
        await abruf.hole(GOOGLE_BOOKS, Frage("https://www.googleapis.com/books/v1/volumes"))
    assert abruf.netz.zahl() == 0


def test_ausweis_ist_ehrlich_und_nennt_nur_einen_eingetragenen_kontakt(monkeypatch):
    monkeypatch.setattr(settings, "quellen_kontakt", "")
    assert ausweis() == f"BuecherFreunde/{settings.version} (self-hosted book library)"
    monkeypatch.setattr(settings, "quellen_kontakt", "https://example.org/ich\r\nX-Boese: 1 (ä)")
    assert ausweis() == f"BuecherFreunde/{settings.version} (self-hosted book library; https://example.org/ichX-Boese: 1)"
    ausweis().encode("ascii")


def test_mit_kontakt_darf_die_app_mehr_und_nie_mehr_als_eingestellt(monkeypatch):
    monkeypatch.setattr(settings, "quellen_kontakt", "")
    assert WIKIPEDIA.minute <= 10 and OPEN_LIBRARY.abstand >= 1
    monkeypatch.setattr(settings, "quellen_kontakt", "https://example.org")
    assert WIKIPEDIA.minute > 10 and OPEN_LIBRARY.abstand == 1.0, "OPENLIBRARY_RATE_LIMIT bremst weiter"
    monkeypatch.setattr(settings, "openlibrary_rate_limit", 3)
    assert OPEN_LIBRARY.abstand == 0.5


def test_jede_quelle_hat_schalter_und_probe():
    assert set(stand.PROBEN) == set(REGELN)
    assert all(hasattr(settings, r.schalter) for r in REGELN.values())


# -- Stand -------------------------------------------------------------------------------------------------------------
async def test_stand_aus_dem_gemerkten_und_probe_hoechstens_einmal_je_minute(test_db, netz):
    netz.setze("services.dnb.de", antwort(b"<x/>"))
    dnb = {s.kennung: s for s in await stand.alle()}["dnb"]
    assert (dnb.stand, dnb.wort, netz.zahl()) == ("aus", "Noch nicht gefragt", 0)
    for _ in range(3):
        dnb = await stand.pruefe("dnb")
    assert netz.zahl() == 1 and dnb.stand == "gut" and dnb.wort.startswith("Zuletzt gut") and dnb.anfragen_heute == 1
    netz.setze("lobid.org", AUSFALL)
    gnd = await stand.pruefe("gnd")
    assert gnd.stand == "schlecht" and gnd.grund == "antwortet nicht rechtzeitig"


async def test_probe_darf_an_der_sicherung_vorbei_aber_nicht_an_der_bitte_um_ruhe(test_db, netz):
    netz.setze("services.dnb.de", AUSFALL)
    for n in range(SICHERUNG_AB):
        with pytest.raises((Ausgefallen, Pausiert)):
            await quellen_abruf.hole(DNB, Frage(FRAGE.adresse, (("query", str(n)),)))
    netz.setze("services.dnb.de", antwort(b"<x/>"))
    assert (await stand.pruefe("dnb")).stand == "gut"
    netz.setze("lobid.org", antwort(status=429, retry_after="600"))
    assert (await stand.pruefe("gnd")).stand == "warn"
    vorher = netz.zahl()
    z = await quellen_abruf.abruf().zustaende.von("gnd")
    z.geprueft_am = None
    assert (await stand.pruefe("gnd")).wort.startswith("Pause bis") and netz.zahl() == vorher
