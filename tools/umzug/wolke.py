"""Kopiert den Bücherbestand in die Kellerwolke (BF-6). Liest nur; am Bestand und an der Datenbank ändert sich nichts.

    python3 wolke.py vorschau                 was entstünde, ohne etwas zu schreiben
    python3 wolke.py kopieren [--nur N]       fortsetzbar; je Buch Original und ein Begleiter (Umschlag, Volltext, Angaben)
    python3 wolke.py rest                     Dateien ohne Eintrag, Autorenfotos, Hintergründe, Datenbanksicherung
    python3 wolke.py pruefen                  jede Prüfsumme gegen die Kellerwolke

Einstellungen aus der Umgebung: BF_DB (Kopie der Datenbank), BF_SPEICHER, BF_STAND (SQLite mit dem Stand), BF_WOLKE
(Adresse), BF_CA, BF_SCHLUESSEL (Datei), BF_ZIEL (Ordner in der Wolke), BF_WOLKE_PID (Prozess zum Drosseln).
Der Name jeder Datei trägt die Nummer des Buchs; Prüfsumme ist der sha256, unter dem das Buch heute abgelegt ist."""
import argparse
import http.client
import io
import json
import os
import re
import sqlite3
import ssl
import sys
import time
import unicodedata
import zipfile
from pathlib import Path
from urllib.parse import quote, urlsplit

U = os.environ
SPEICHER, ZIEL = Path(U.get("BF_SPEICHER", "/mnt/data/buecher")), U.get("BF_ZIEL", "Apps/BücherFreunde")
NEBEN = {"cover.jpg", "fulltext.txt", "metadata.json", "seiten.json"}
FORMATE = {".pdf", ".epub", ".mobi", ".txt", ".md"}
VERBOTEN = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')


class Wolke:
    """Schmale Verbindung zur Ablage; jede Anfrage neu aufgebaut, wenn die alte abriss."""

    def __init__(self) -> None:
        self.teile = urlsplit(U["BF_WOLKE"])
        self.kopf = {"Authorization": "Bearer " + Path(U["BF_SCHLUESSEL"]).read_text().strip()}
        self.ssl = ssl.create_default_context(cafile=U.get("BF_CA") or None)
        self.v = None

    def rufe(self, art: str, weg: str, koerper=None, kopf=None, laenge=None):
        for versuch in range(5):
            try:
                if self.v is None:
                    self.v = http.client.HTTPSConnection(self.teile.hostname, self.teile.port or 443, context=self.ssl, timeout=300)
                if hasattr(koerper, "seek"):
                    koerper.seek(0)
                k = {**self.kopf, **(kopf or {})}
                if laenge is not None:
                    k["Content-Length"] = str(laenge)
                self.v.request(art, quote(weg, safe="/?&=%"), body=koerper, headers=k)
                r = self.v.getresponse()
                daten = r.read()
                if r.status in (502, 503, 504):
                    raise OSError(f"HTTP {r.status}")
                if r.status >= 400 and koerper is not None:      # abgelehnt, ohne alles zu lesen: der Rest läge sonst vor der nächsten Anfrage
                    self.v.close()
                    self.v = None
                return r.status, (json.loads(daten) if daten and "json" in (r.headers.get("content-type") or "") else daten)
            except (OSError, http.client.HTTPException) as f:
                self.v = None
                if versuch == 4:
                    raise
                print(f"  Verbindung ({type(f).__name__}: {f}), neuer Versuch", flush=True)
                time.sleep(5 * (versuch + 1))

    def ablegen(self, pfad: str, datei: Path):
        """Legt eine Datei ab, wenn unter dem Pfad noch keine liegt; sonst gilt die vorhandene. Erst nachsehen: eine
        Ablehnung kommt, bevor die Ablage den Inhalt liest, und ließe die Verbindung mitten im Senden abreißen."""
        weg = "/api/v1/ablage/pfad?pfad=" + quote(pfad, safe="")
        st, d = self.rufe("GET", weg)
        if st < 400:
            return st, d
        with datei.open("rb") as f:
            st, d = self.rufe("PUT", f"/api/v1/ablage/datei?pfad={quote(pfad, safe='')}", f,
                              {"If-None-Match": "*", "Content-Type": "application/octet-stream"}, datei.stat().st_size)
        if st in (409, 412):
            st, d = self.rufe("GET", weg)
        return st, d

    def ordner(self, pfad: str) -> None:
        st, d = self.rufe("POST", "/api/v1/ablage/ordner", json.dumps({"pfad": pfad}).encode(), {"Content-Type": "application/json"})
        if st >= 400:
            raise SystemExit(f"Ordner {pfad}: {st} {d}")


def sauber(text: str, hoechstens: int) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = re.sub(r"\s+", " ", VERBOTEN.sub(" ", t)).strip(" .")
    while len(t.encode()) > hoechstens:
        t = t[:-1].rstrip(" .")
    return t


def ablageort(b) -> str:
    titel = sauber(b["title"], 110) or sauber(Path(b["file_name"] or "").stem, 110) or "Ohne Titel"
    autor = sauber(b["author"], 60)
    a = unicodedata.normalize("NFD", titel)[0].upper()
    fach = a if "A" <= a <= "Z" else ("0-9" if a.isdigit() else "Andere")
    endung = (b["file_format"] or "bin").lower()
    return f"{ZIEL}/Bücher/{fach}/{titel}{' - ' + autor if autor else ''} [{b['id']}].{endung}"


def original(b) -> Path | None:
    o = SPEICHER / b["hash"][:2] / b["hash"][2:4] / b["hash"]
    if not o.is_dir():
        return None
    kand = [f for f in o.iterdir() if f.is_file() and f.name not in NEBEN]
    return next((f for f in kand if f.name == b["file_name"]), None) or next((f for f in kand if f.suffix.lower() in FORMATE), None)


def db():
    c = sqlite3.connect(f"file:{U['BF_DB']}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def stand():
    c = sqlite3.connect(U["BF_STAND"])
    c.execute("CREATE TABLE IF NOT EXISTS datei(buch INTEGER PRIMARY KEY, hash TEXT, knoten TEXT, pfad TEXT, groesse INTEGER, sha256 TEXT, begleiter TEXT, fertig_am TEXT, fehler TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS rest(quelle TEXT PRIMARY KEY, knoten TEXT, pfad TEXT, sha256 TEXT)")
    c.commit()
    return c


def angaben(c, b) -> dict:
    zeile = {k: b[k] for k in b.keys() if k not in ("fts_content", "storage_path")}
    alle = lambda s: [dict(r) for r in c.execute(s, (b["id"],))]
    return {"art": "buecherfreunde-angaben/1", "buch": zeile,
            "kategorien": [r["name"] for r in c.execute("SELECT c.name FROM categories c JOIN book_categories x ON x.category_id=c.id WHERE x.book_id=?", (b["id"],))],
            "lesen": alle("SELECT * FROM user_book_data WHERE book_id=?"), "notizen": alle("SELECT * FROM book_notes WHERE book_id=?"),
            "markierungen": alle("SELECT * FROM book_highlights WHERE book_id=?"), "labels": alle("SELECT * FROM book_labels WHERE book_id=?")}


def begleiter(c, b, quelle: Path) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n in ("cover.jpg", "fulltext.txt", "seiten.json", "metadata.json"):
            f = quelle.parent / n
            if f.is_file():
                z.write(f, n, zipfile.ZIP_STORED if n == "cover.jpg" else zipfile.ZIP_DEFLATED)
        z.writestr("angaben.json", json.dumps(angaben(c, b), ensure_ascii=False, indent=1, default=str))
    return puffer.getvalue()


def rechenzeit(pid: str) -> float:
    f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")


def drosseln(hoechstens_s: float) -> None:
    """Wartet, bis die Kellerwolke mit dem Zerlegen der letzten Datei fertig ist, damit sie für Menschen flink bleibt."""
    pid = U.get("BF_WOLKE_PID")
    if not pid:
        return
    ende = time.time() + hoechstens_s
    while time.time() < ende:
        a = rechenzeit(pid)
        time.sleep(.6)
        if (rechenzeit(pid) - a) / .6 < .35:
            return


def kopiere(w: Wolke, c, s, b) -> str:
    q = original(b)
    if q is None:
        return "Original fehlt auf der Platte"
    pfad, gr = ablageort(b), q.stat().st_size
    st, d = w.ablegen(pfad, q)
    if st >= 400:
        return f"Ablegen: {st} {d}"
    if d["sha256"] != b["hash"]:
        return f"Prüfsumme {d['sha256']} statt {b['hash']}"
    knoten = d["id"]
    w.rufe("PATCH", f"/api/v1/ablage/knoten/{knoten}/felder", json.dumps({"felder": {"buch": b["id"], "titel": b["title"], "autor": b["author"]}}).encode(), {"Content-Type": "application/json"})
    inhalt = begleiter(c, b, q)
    st, d = w.rufe("PUT", f"/api/v1/ablage/knoten/{knoten}/begleiter/auszug?zusatz=.auszug.zip", inhalt, {"If-None-Match": "*", "Content-Type": "application/zip"}, len(inhalt))
    if st in (409, 412):
        st, alle = w.rufe("GET", f"/api/v1/ablage/knoten/{knoten}/begleiter")
        d = next((x for x in alle if x["rolle"] == "auszug"), {}) if st < 400 else {}
    if st >= 400 or not d.get("id"):
        return f"Begleiter: {st} {d}"
    s.execute("INSERT OR REPLACE INTO datei VALUES(?,?,?,?,?,?,?,datetime('now'),NULL)", (b["id"], b["hash"], knoten, pfad, gr, b["hash"], d["id"]))
    s.commit()
    drosseln(90 if b["file_format"] == "pdf" else 5)
    return ""


def buecher(c):
    return c.execute("SELECT * FROM books ORDER BY (file_format='pdf'), file_size").fetchall()


def vorschau() -> None:
    c, alle = db(), None
    alle = buecher(c)
    ohne = [b for b in alle if original(b) is None]
    pfade = [ablageort(b) for b in alle]
    faecher = {}
    for p in pfade:
        faecher[p.split("/")[-2]] = faecher.get(p.split("/")[-2], 0) + 1
    print("Bücher", len(alle), "ohne Original", [(b["id"], b["title"]) for b in ohne], "doppelte Pfade", len(pfade) - len(set(p.lower() for p in pfade)), "längster Name", max(len(p.rsplit("/", 1)[1].encode()) for p in pfade))
    print("Fächer", dict(sorted(faecher.items())))
    print("Beispiele", *pfade[:3], *pfade[-3:], sep="\n  ")
    bekannt = {b["hash"] for b in alle}
    fremd = [o for o in SPEICHER.glob("[0-9a-f][0-9a-f]/*/*") if o.name not in bekannt]
    quar = [f for f in (SPEICHER / "_quarantaene").rglob("*") if f.is_file() and f.suffix.lower() in FORMATE and f.name not in NEBEN]
    print("Ordner ohne Eintrag", len(fremd), "in Quarantäne", len(quar))


def kopieren(nur: int | None) -> None:
    w, c, s = Wolke(), db(), stand()
    fertig = {r[0] for r in s.execute("SELECT buch FROM datei WHERE fehler IS NULL")}
    offen = [b for b in buecher(c) if b["id"] not in fertig][:nur]
    for fach in sorted({ablageort(b).rsplit("/", 1)[0] for b in offen}):
        w.ordner(fach)
    summe, erledigt, beginn = sum(b["file_size"] or 0 for b in offen), 0, time.time()
    print(f"offen {len(offen)} Bücher, {summe / 1e9:.2f} GB, schon da {len(fertig)}", flush=True)
    for n, b in enumerate(offen, 1):
        grund = kopiere(w, c, s, b)
        erledigt += b["file_size"] or 0
        if grund:
            s.execute("INSERT OR REPLACE INTO datei(buch,hash,fehler) VALUES(?,?,?)", (b["id"], b["hash"], grund))
            s.commit()
            print(f"FEHLER {b['id']} {b['title'][:60]}: {grund}", flush=True)
        if n % 25 == 0 or n == len(offen):
            print(f"{time.strftime('%H:%M:%S')} {n}/{len(offen)} {erledigt / 1e9:.2f}/{summe / 1e9:.2f} GB, {(time.time() - beginn) / 60:.0f} min", flush=True)


def rest() -> None:
    w, c, s = Wolke(), db(), stand()
    bekannt = {b["hash"] for b in c.execute("SELECT hash FROM books")}
    quellen = []
    for o in SPEICHER.glob("[0-9a-f][0-9a-f]/*/*"):
        if o.name not in bekannt:
            quellen += [(f, f"Ohne Eintrag/{o.name[:12]} {f.name}") for f in o.iterdir() if f.is_file() and f.suffix.lower() in FORMATE and f.name not in NEBEN]
    quellen += [(f, f"Quarantäne/{f.parent.name[:12]} {f.name}") for f in (SPEICHER / "_quarantaene").rglob("*") if f.is_file() and f.name not in NEBEN]
    quellen += [(f, f"Autoren/{f.relative_to(SPEICHER / 'authors')}") for f in (SPEICHER / "authors").rglob("*") if f.is_file()]
    if U.get("BF_HINTERGRUND"):
        quellen += [(f, f"Hintergründe/{f.name}") for f in Path(U["BF_HINTERGRUND"]).glob("*") if f.is_file()]
    quellen.append((Path(U["BF_DB"]), f"Sicherung/{Path(U['BF_DB']).name}"))
    for f, ziel in quellen:
        if s.execute("SELECT 1 FROM rest WHERE quelle=?", (str(f),)).fetchone():
            continue
        teile = [sauber(t, 170) for t in ziel.split("/")]
        pfad = f"{ZIEL}/" + "/".join(teile)
        w.ordner(pfad.rsplit("/", 1)[0])
        st, d = w.ablegen(pfad, f)
        if st >= 400:
            print("FEHLER", f, st, d, flush=True)
            continue
        s.execute("INSERT OR REPLACE INTO rest VALUES(?,?,?,?)", (str(f), d["id"], pfad, d["sha256"]))
        s.commit()
    print("Rest fertig:", s.execute("SELECT COUNT(*) FROM rest").fetchone()[0], "von", len(quellen))


def pruefen() -> None:
    w, c, s = Wolke(), db(), stand()
    soll = {b["id"]: b for b in buecher(c)}
    gut = falsch = 0
    for r in s.execute("SELECT buch, hash, knoten, begleiter FROM datei WHERE fehler IS NULL").fetchall():
        st, d = w.rufe("GET", f"/api/v1/ablage/knoten/{r[2]}")
        ok = st == 200 and d["sha256"] == r[1] == soll[r[0]]["hash"]
        gut, falsch = gut + ok, falsch + (not ok)
        if not ok:
            print("FALSCH", r[0], st, flush=True)
    print(f"geprüft {gut} gut, {falsch} falsch, erwartet {len(soll)}, offen {len(soll) - gut}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("was", choices=["vorschau", "kopieren", "rest", "pruefen"])
    p.add_argument("--nur", type=int)
    a = p.parse_args()
    sys.exit({"vorschau": vorschau, "kopieren": lambda: kopieren(a.nur), "rest": rest, "pruefen": pruefen}[a.was]())
