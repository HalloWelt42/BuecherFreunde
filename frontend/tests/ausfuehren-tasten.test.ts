// Ausführen (BF-29): Fassung zum Wunsch, Bestand je Fassung, Codestellen im Text finden, gefärbte Zeilen, Listing aus Stelle
import type { Codestelle } from "../src/lib/api/ausfuehren";
import { bestandFuer, passendeFassung } from "../src/lib/ausfuehren/fassungen";
import { inZeilen } from "../src/lib/ausfuehren/zeilen";
import { listingAus } from "../src/lib/leser/codestellen.svelte";
import { codebloecke, zeilenbereich } from "../src/lib/leser/text/codeorte";

function stelle(teil: Partial<Codestelle>): Codestelle {
  return {
    kennung: "z5-ab", teile: [{ seite: null, rechteck: null, offen_oben: false, offen_unten: false, kapitel: null, nr: null, zeile: 5 }],
    sprache: "python", sicherheit: 1, quelle: "auszeichnung", titel: "", datei: "", code: "print(1)", zeilennummern_ab: null,
    pruefsumme: "p", ausfuehrbar: true, vorpruefung: null, ...teil,
  };
}

describe("Fassungen", () => {
  const FASSUNGEN = ["8.5", "8.4", "8.3", "7.4"];
  it("nimmt den Wunsch, sonst die neueste der Reihe, sonst die nächstältere, ohne Wunsch die neueste", () => {
    expect(passendeFassung(FASSUNGEN, "8.4")).toBe("8.4");
    expect(passendeFassung(FASSUNGEN, "8")).toBe("8.5");
    expect(passendeFassung(FASSUNGEN, "8.0")).toBe("7.4");
    expect(passendeFassung(FASSUNGEN, "")).toBe("8.5");
    expect(passendeFassung(FASSUNGEN, "5.6")).toBe("7.4");
    expect(passendeFassung([], "8.4")).toBe("");
  });
  it("sagt, ab oder bis wann es eine Funktion gibt", () => {
    const b = bestandFuer("PHP", "8.3", { "8.4": ["array_find", "strlen"], "8.3": ["strlen"], "7.4": ["strlen", "each"] });
    expect(b?.pruefe("strlen")).toBeNull();
    expect(b?.pruefe("array_find")).toBe("array_find() gibt es erst ab PHP 8.4, gewählt ist PHP 8.3");
    expect(b?.pruefe("each")).toBe("each() gibt es nur bis PHP 7.4, gewählt ist PHP 8.3");
    expect(b?.pruefe("eigene")).toBeNull();
    expect(bestandFuer("PHP", "9.0", {})).toBeNull();
  });
});

describe("Codestellen im Text", () => {
  it("findet Codeblöcke, deren Text eine Stelle ist, gleich wie Färbung und Einrückung den Leerraum setzen", () => {
    document.body.innerHTML = `<pre><code><span>for</span> x <span>in</span> y:\n    print(x)\n</code></pre><pre><code>anderes()</code></pre>`;
    const s = stelle({ code: "for x in y:\n  print(x)" });
    const gefunden = codebloecke(document.body, [s]);
    expect(gefunden).toHaveLength(1);
    expect(gefunden[0].stelle).toBe(s);
    expect(gefunden[0].teil).toBe(0);
    expect(codebloecke(document.body, [])).toEqual([]);
  });
  it("legt den Anfang einer Zeile im schlichten Text über Blöcke hinweg als Bereich", () => {
    document.body.innerHTML = `<p class="schlichttext">eins\nzwei</p><p class="schlichttext">drei\n\`\`\`python\nprint(1)</p>`;
    const bloecke = [...document.querySelectorAll(".schlichttext")];
    expect(zeilenbereich(bloecke, 2)?.toString()).toBe("zwei");
    expect(zeilenbereich(bloecke, 4)?.toString()).toBe("```python");
    expect(zeilenbereich(bloecke, 9)).toBeNull();
  });
});

describe("Gefärbte Zeilen", () => {
  it("schließt eine Spanne über mehrere Zeilen am Zeilenende und öffnet sie in der nächsten wieder", () => {
    expect(inZeilen(`a <span class="s">"x\ny"</span> b\nc`)).toEqual([`a <span class="s">"x</span>`, `<span class="s">y"</span> b`, "c"]);
  });
});

describe("Listing aus einer Stelle", () => {
  it("nimmt die Datei aus dem Titel, kürzt Buch- und Kastentitel und fällt bei fremder Sprache auf Python", () => {
    const l = listingAus(stelle({ titel: "Ausprobieren - kap01/schaetzer.py", sprache: "python" }), { id: 7, title: "Neuronale Netze - Eine Einführung" }, "/book/7/read?page=20", "8-9");
    expect(l).toMatchObject({ buch: 7, buchtitel: "Neuronale Netze", titel: "Ausprobieren", datei: "kap01/schaetzer.py", seiten: "8-9", adresse: "/book/7/read?page=20" });
    expect(listingAus(stelle({ sprache: "ruby" }), { id: 7, title: "X" }, "").sprache).toBe("python");
    expect(listingAus(stelle({ datei: "eigen.php", titel: "Listing 2" }), { id: 7, title: "X" }, "").datei).toBe("eigen.php");
  });
});
