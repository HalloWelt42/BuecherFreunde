"""Ein erfundenes Fachbuch als EPUB für die Tests der Übersetzung (BF-71): Überschriften, Absätze, Listen, Tabelle, Code,
Bild, Fußnote, Verweise, Kommentare, Zeichenreferenzen, Inhaltsverzeichnis (nav und NCX). Alle Texte sind selbst geschrieben."""

from __future__ import annotations

import io
import zipfile

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="kennung" xml:lang="en">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="kennung">urn:uuid:00000000-0000-4000-8000-000000000071</dc:identifier>
    <dc:title>Gardening with Small Machines</dc:title>
    <dc:creator>Ada Example</dc:creator>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="umschlag" href="text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="kap1" href="text/kapitel%201.xhtml" media-type="application/xhtml+xml"/>
    <item id="kap2" href="text/kap2.xhtml" media-type="application/xhtml+xml"/>
    <item id="bild" href="bilder/garten.png" media-type="image/png"/>
    <item id="stil" href="stil.css" media-type="text/css"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="umschlag"/>
    <itemref idref="kap1"/>
    <itemref idref="kap2"/>
  </spine>
</package>
"""

NAV = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head><title>Contents</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Contents</h1>
    <ol>
      <li><a href="text/kapitel%201.xhtml">Getting Started</a></li>
      <li><a href="text/kap2.xhtml#teil">Watering the Beds</a></li>
    </ol>
  </nav>
</body>
</html>
"""

NCX = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="en">
  <head><meta name="dtb:uid" content="urn:uuid:00000000-0000-4000-8000-000000000071"/></head>
  <docTitle><text>Gardening with Small Machines</text></docTitle>
  <navMap>
    <navPoint id="p1" playOrder="1"><navLabel><text>Getting Started</text></navLabel><content src="text/kapitel%201.xhtml"/></navPoint>
    <navPoint id="p2" playOrder="2"><navLabel><text>Watering the Beds</text></navLabel><content src="text/kap2.xhtml#teil"/></navPoint>
  </navMap>
</ncx>
"""

UMSCHLAG = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head><title>Cover</title></head>
<body><div class="umschlag"><img src="../bilder/garten.png" alt="cover"/></div></body>
</html>
"""

KAPITEL_1 = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
  <title>Getting Started</title>
  <link rel="stylesheet" type="text/css" href="../stil.css"/>
</head>
<body>
<section id="start" epub:type="chapter">
  <h1 id="h1">Getting Started</h1>
  <p>A small machine can water <em>16,000</em> plants in 1.5 hours, which is about 3&#160;GB of logs.<a epub:type="noteref" href="#fn1" id="r1">1</a></p>
  <p>Call <code>water_all()</code> before you start the <strong>pump</strong> &amp; check the
     <a href="kap2.xhtml#teil">next chapter</a> for details.</p>
  <!-- ein Kommentar zwischen den Absätzen -->
  <p>The garden&#8217;s soil is <span translate="no">Erdreich</span> in our notes.</p>
  <ul>
    <li>Fill the tank<ul><li>use clean water</li></ul> before the first run</li>
    <li><p>Check the <b>filter <i>twice</i></b> a week.</p></li>
  </ul>
  <table>
    <caption>Daily water needs</caption>
    <tr><th>Plant</th><th>Litres</th></tr>
    <tr><td>Tomato</td><td>2</td></tr>
  </table>
  <pre><code>pump.start(speed=3)  # never translated</code></pre>
  <div class="programlisting">print("stays as it is")</div>
  <figure><img src="../bilder/garten.png" alt="A garden"/><figcaption>A garden at dawn.</figcaption></figure>
  <p>Visit <a href="https://example.org/garden">https://example.org/garden</a></p>
  <aside epub:type="footnote" id="fn1"><p><a epub:type="backlink" href="#r1">1</a> Measured on a dry day.</p></aside>
</section>
</body>
</html>
"""

KAPITEL_2 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head><title>Watering the Beds</title></head>
<body>
  <h2 id="teil">Watering the Beds</h2>
  <blockquote>Water early, water deep.</blockquote>
  <dl><dt>Bed</dt><dd>A raised box of soil.</dd></dl>
  <p>Done.<br/>Now rest.</p>
</body>
</html>
"""

STIL = "p { margin: 0; }\n"
BILD = b"\x89PNG\r\n\x1a\n" + bytes(range(64))

DATEIEN = {
    "META-INF/container.xml": CONTAINER, "OEBPS/content.opf": OPF, "OEBPS/nav.xhtml": NAV, "OEBPS/toc.ncx": NCX,
    "OEBPS/text/cover.xhtml": UMSCHLAG, "OEBPS/text/kapitel 1.xhtml": KAPITEL_1, "OEBPS/text/kap2.xhtml": KAPITEL_2,
    "OEBPS/bilder/garten.png": BILD, "OEBPS/stil.css": STIL,
}


def probe_epub(ersetzt: dict[str, str | bytes] | None = None) -> bytes:
    """Das Probebuch als EPUB; `ersetzt` tauscht den Inhalt einzelner Dateien (Pfad im Archiv -> Inhalt)."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype", date_time=(2026, 1, 1, 0, 0, 0)), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for pfad, inhalt in DATEIEN.items():
            inhalt = (ersetzt or {}).get(pfad, inhalt)
            daten = inhalt if isinstance(inhalt, bytes) else inhalt.encode("utf-8")
            z.writestr(zipfile.ZipInfo(pfad, date_time=(2026, 1, 1, 0, 0, 0)), daten, compress_type=zipfile.ZIP_DEFLATED)
    return puffer.getvalue()


def dateien(epub: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(epub)) as z:
        return {i.filename: z.read(i.filename) for i in z.infolist()}
