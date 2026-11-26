// Eigenes Kontextmenü (BF-42): überall statt des Menüs des Browsers, außer in Feldern zum Schreiben und im Editor
import { kontext, kontextmenue, type Anbieter } from "../src/lib/stand/kontextmenue.svelte";

function element(html: string): HTMLElement {
  const d = document.createElement("div");
  d.innerHTML = html;
  document.body.append(d);
  return d.firstElementChild as HTMLElement;
}

function rechtsklick(ziel: Element, finger = false): Event {
  const e = finger
    ? new PointerEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 40, clientY: 50, pointerType: "touch" })
    : new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 40, clientY: 50 });
  ziel.dispatchEvent(e);
  return e;
}

const warte = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  kontextmenue.schliesse();
  getSelection()?.removeAllRanges();
  document.body.innerHTML = "";
});

describe("Kontextmenü", () => {
  it("zeigt die Einträge des Bausteins unter der Maus, am Punkt des Klicks", async () => {
    const karte = element("<div><span>Titel</span></div>");
    const tun = vi.fn();
    const anbieter: Anbieter = () => [{ text: "Öffnen", symbol: "book", tun }];
    kontext(karte, anbieter);
    const e = rechtsklick(karte.querySelector("span")!);
    await warte();
    expect(e.defaultPrevented).toBe(true);
    expect(kontextmenue.offen).toMatchObject({ x: 40, y: 50, eintraege: [{ text: "Öffnen" }] });
  });

  it("lässt Feldern zum Schreiben und dem Editor das Menü des Browsers", async () => {
    for (const html of ["<input>", "<textarea></textarea>", '<div contenteditable="true">x</div>', '<div class="cm-editor"><div class="cm-line">x</div></div>']) {
      const feld = element(html);
      const e = rechtsklick(feld.querySelector(".cm-line") ?? feld);
      await warte();
      expect(e.defaultPrevented).toBe(false);
      expect(kontextmenue.offen).toBeNull();
    }
  });

  it("bietet ohne eigenen Baustein für markierten Text Kopieren an, und das kopiert wirklich", async () => {
    const schreibe = vi.fn(async () => {});
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: schreibe } });
    const p = element("<p>Ein ganzer Satz zum Kopieren</p>");
    const r = document.createRange();
    r.setStart(p.firstChild!, 4);
    r.setEnd(p.firstChild!, 10);
    getSelection()!.addRange(r);
    rechtsklick(p);
    await warte();
    expect(kontextmenue.offen?.eintraege.map((e) => e.text)).toEqual(["Kopieren"]);
    await kontextmenue.offen!.eintraege[0].tun!();
    expect(schreibe).toHaveBeenCalledWith("ganzer");
    vi.unstubAllGlobals();
  });

  it("bietet für einen Verweis Öffnen, neuen Tab und die Adresse an", async () => {
    const a = element('<a href="/book/5">Buch</a>');
    rechtsklick(a);
    await warte();
    expect(kontextmenue.offen?.eintraege.map((e) => e.text)).toEqual(["Öffnen", "In neuem Tab öffnen", "Adresse kopieren"]);
  });

  it("zeigt der Maus nie das Menü des Browsers, auch wo es nichts anzubieten gibt", async () => {
    const e = rechtsklick(element("<div>leer</div>"));
    await warte();
    expect(e.defaultPrevented).toBe(true);
    expect(kontextmenue.offen).toBeNull();
  });

  it("nimmt das Wort weg, das erst der Rechtsklick gewählt hat, und zeigt das Menü ohne Auswahl", async () => {
    const leser = element("<div><p>Text im Buch</p></div>");
    kontext(leser, (e) => ((e.view ?? window).getSelection()?.toString() ? "eigen" : [{ text: "Vorlesen ab hier", symbol: "play" }]));
    const p = leser.querySelector("p")!;
    p.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, button: 2 }));
    const r = document.createRange();
    r.setStart(p.firstChild!, 0);
    r.setEnd(p.firstChild!, 4);
    getSelection()!.addRange(r);
    rechtsklick(p);
    await warte();
    expect(getSelection()!.isCollapsed).toBe(true);
    expect(kontextmenue.offen?.eintraege.map((e) => e.text)).toEqual(["Vorlesen ab hier"]);
  });

  it("lässt langes Drücken ohne Angebot dem Browser, damit die Auswahl im Text geht", async () => {
    const leser = element("<div><p>Text im Buch</p></div>");
    kontext(leser, (_, finger) => (finger ? null : [{ text: "Vorlesen ab hier", symbol: "play" }]));
    const e = rechtsklick(leser.querySelector("p")!, true);
    await warte();
    expect(e.defaultPrevented).toBe(false);
    expect(kontextmenue.offen).toBeNull();
  });

  it("schweigt, wenn der Baustein sein eigenes Menü zeigt (Auswahl im Leser)", async () => {
    const leser = element("<div><p>Text</p></div>");
    kontext(leser, () => "eigen");
    const e = rechtsklick(leser.querySelector("p")!);
    await warte();
    expect(e.defaultPrevented).toBe(true);
    expect(kontextmenue.offen).toBeNull();
  });
});
