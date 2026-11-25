import { entschaerfe, hinweiskasten, mitDiagramm, sichereAdresse } from "../src/lib/leser/text/markdown";
import { prozentVon, textkapitel, zeichneMarkierungen, zeichneTreffer } from "../src/lib/leser/text/markierung";
import { findeStuecke } from "../src/lib/leser/textsuche";
import { hexZuTon, tonZuHex } from "../src/lib/farbton";
import { gleicheSchrift, istDunkel, klemme, papierOder, themaIndex, ZEILEN } from "../src/lib/leser/darstellung";
import type { Markierung } from "../src/lib/typen";

const blatt = (html: string) => {
  const d = document.createElement("div");
  d.innerHTML = html;
  return d;
};
const marke = (id: number, text: string, prozent: number): Markierung => ({ id, book_id: 1, cfi_range: `percent:${prozent}`, color: "#66BB6A", text_snippet: text, label_name: "", label_note: "", created_at: "" });

describe("Markdown", () => {
  it("macht gefährliches HTML zu Text und lässt harmlose Tags", () => {
    expect(entschaerfe('<img src=x onerror=alert(1)> <b>fett</b> <script>x</script>')).toBe('\\<img src=x onerror=alert(1)> <b>fett</b> \\<script>x\\</script>');
    expect(entschaerfe("<b onmouseover=x>")).toBe("\\<b onmouseover=x>");
  });

  it("rührt Code und Verweise nicht an", () => {
    expect(entschaerfe("`<b onclick>` und\n```html\n<script>\n```\n<https://example.org>")).toBe("`<b onclick>` und\n```html\n<script>\n```\n<https://example.org>");
    expect(entschaerfe("a < b und 3 > 2")).toBe("a < b und 3 > 2");
  });

  it("kennt beide Schreibweisen der Hinweiskästen", () => {
    const { tokenizer } = hinweiskasten().extensions[0];
    expect(tokenizer("> [!bug] Heiß\n")).toMatchObject({ alertType: "caution", text: "Heiß" });
    expect(tokenizer("> [!NOTE]\n> Eins\n> Zwei\n")).toMatchObject({ alertType: "note", text: "Eins\nZwei" });
    expect(tokenizer("> [!unbekannt] x")).toBeUndefined();
  });

  it("lässt nur Adressen zu, die nichts ausführen", () => {
    expect(sichereAdresse("javascript:alert(1)")).toBe("");
    expect(sichereAdresse(" https://example.org ")).toBe("https://example.org");
    expect(sichereAdresse("#teil-2")).toBe("#teil-2");
    expect(mitDiagramm("x\n```mermaid\ngraph")).toBe(true);
    expect(mitDiagramm("mermaid im Satz")).toBe(false);
  });
});

describe("Markierungen im Text", () => {
  // jsdom kennt keine Hervorhebungen: hier malt die Schicht aus Rechtecken, gezählt werden die Bereiche
  it("findet über Elementgrenzen die Stelle, die am nächsten liegt, und lässt den Text unberührt", () => {
    const b = blatt("<p>Ein Deich am Meer.</p><p>Noch ein <b>Deich</b> im Land.</p>");
    const vorher = b.innerHTML;
    const r = zeichneMarkierungen(b, [marke(3, "Deich", 70)]);
    expect([r.get(3)?.toString(), r.get(3)?.startContainer.parentElement?.tagName]).toEqual(["Deich", "B"]);
    expect(zeichneMarkierungen(b, [marke(4, "ein Deich im", 60)]).get(4)?.toString()).toBe("ein Deich im");
    expect(zeichneMarkierungen(b, []).size).toBe(0);
    expect(b.innerHTML).toBe(vorher);
  });

  it("zeichnet Treffer in Lesefolge", () => {
    const b = blatt("<p>Salz und Pfeffer, Salz und Essig</p><p>salzig</p>");
    expect(zeichneTreffer(b, "salz").map((t) => t.toString())).toEqual(["Salz", "Salz", "salz"]);
    expect(zeichneTreffer(b, "")).toEqual([]);
    expect(b.querySelector("mark")).toBeNull();
  });

  it("liest Prozentstellen und erkennt Überschriften in schlichtem Text", () => {
    expect(prozentVon("percent:51.7")).toBe(51.7);
    expect(prozentVon("epubcfi(/6)")).toBeNull();
    expect(textkapitel(["Kapitel 1", "", "Text", "", "Kapitel 2 Der Deich", "", "Text"]).map((k) => k.titel)).toEqual(["Kapitel 1", "Kapitel 2 Der Deich"]);
    expect(textkapitel(["nur Text", "noch mehr"])).toEqual([]);
  });

  it("findet Stücke auch mit kürzerem Anfang", () => {
    expect(findeStuecke(["abc def", "ghi jkl"], "defghi")).toEqual({ von: 0, bis: 2 });
    expect(findeStuecke(["Anfang der langen Stelle hier", "anders weiter"], "Anfang der langen Stelle hier und dann ganz anders als gedacht")).toEqual({ von: 0, bis: 2 });
    expect(findeStuecke(["x"], "a")).toBeNull();
  });
});

describe("Darstellung", () => {
  it("rechnet Farben hin und zurück", () => {
    for (const f of ["#f4ecd8", "#1e1e1e", "#3d2b1f", "#ff0000"]) {
      const h = tonZuHex(hexZuTon(f));
      const ab = (i: number) => Math.abs(Number.parseInt(f.slice(i, i + 2), 16) - Number.parseInt(h.slice(i, i + 2), 16));
      expect(Math.max(ab(1), ab(3), ab(5))).toBeLessThanOrEqual(3);
    }
  });

  it("erkennt Themen, Schriften und dunklen Grund", () => {
    expect(themaIndex("#c8c8c8", "#1e1e1e")).toBe(3);
    expect(gleicheSchrift('"Literata", Georgia, serif', "Literata")).toBe(true);
    expect(istDunkel("#3d3526")).toBe(true);
    expect(istDunkel("#f4ecd8")).toBe(false);
    expect(papierOder("", true)).toBe("dunkel");
    expect(papierOder("sepia", true)).toBe("sepia");
    expect(klemme(1.6499, ZEILEN)).toBe(1.6);
    expect(klemme(9, ZEILEN)).toBe(3);
  });
});
