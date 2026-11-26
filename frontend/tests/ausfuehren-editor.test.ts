// Haltepunkte im Editor des Appkerns (BF-29): gemerkte setzt das Fenster von außen; was es nicht gibt, fällt still weg
import { render, waitFor } from "@testing-library/svelte";
import { EditorBereich, erstelleEditor, haltepunkteSchalten, haltepunkteSetzen, haltepunkteVon } from "appkern-oberflaeche/code";

const CODE = "a = 1\nb = 2\nprint(a + b)\n";

/** Gesetzte Punkte in der Rinne, ohne den unsichtbaren Platzhalter, der ihre Breite hält */
const punkte = (wurzel: HTMLElement) =>
  [...wurzel.querySelectorAll<HTMLElement>(".cm-haltepunkt")].filter((p) => p.closest<HTMLElement>(".cm-gutterElement")?.style.visibility !== "hidden").length;

describe("Haltepunkte von außen", () => {
  it("setzt sie in die Rinne, meldet sie wie nach einem Klick und verwirft Zeilen jenseits des Codes", () => {
    const ort = document.createElement("div");
    const view = erstelleEditor({ parent: ort, sprache: "python", initialerCode: CODE, beiAenderung: () => {} });
    const gemeldet: number[][] = [];
    haltepunkteSchalten(view, (zeilen) => gemeldet.push(zeilen));
    haltepunkteSetzen(view, [3, 1, 3, 50, 0]);
    expect(haltepunkteVon(view)).toEqual([1, 3]);
    expect(gemeldet.at(-1)).toEqual([1, 3]);
    haltepunkteSetzen(view, []);
    expect(haltepunkteVon(view)).toEqual([]);
    view.destroy();
  });

  it("wirkt ohne Rinne nicht", () => {
    const view = erstelleEditor({ parent: document.createElement("div"), sprache: "python", initialerCode: CODE, beiAenderung: () => {} });
    haltepunkteSetzen(view, [1]);
    expect(haltepunkteVon(view)).toEqual([]);
    view.destroy();
  });

  it("übernimmt im EditorBereich die Haltepunkte, mit denen er beginnt", async () => {
    const { container } = render(EditorBereich, { props: { sprache: "python", code: CODE, mitHaltepunkten: true, haltepunkte: [2, 99] } });
    await waitFor(() => expect(punkte(container)).toBe(1));
  });

  it("beginnt ohne gemerkte Haltepunkte leer wie bisher", async () => {
    const { container } = render(EditorBereich, { props: { sprache: "python", code: CODE, mitHaltepunkten: true } });
    await waitFor(() => expect(container.querySelector(".cm-haltepunkt-rinne")).toBeTruthy());
    expect(punkte(container)).toBe(0);
  });
});
