// Offene Felder (BF-39): ein Druck daneben und Esc schließen das zuletzt geöffnete, ohne im Buch zu blättern
import { offenesFeld } from "../src/lib/flucht";

function element(tag = "div"): HTMLElement {
  const e = document.createElement(tag);
  document.body.append(e);
  return e;
}

const druecke = (ziel: Element) => ziel.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0 }));

describe("Ein Druck daneben", () => {
  it("schließt das Feld, ein Druck hinein und auf seinen Knopf nicht", () => {
    const feld = element();
    const knopf = element("button");
    const buch = element();
    let zu = 0;
    const ab = offenesFeld(() => [feld, knopf], () => zu++);
    druecke(feld);
    druecke(knopf);
    expect(zu).toBe(0);
    druecke(buch);
    expect(zu).toBe(1);
    ab();
  });

  it("schließt nur das zuletzt geöffnete, je Druck eines", () => {
    const aussen = element();
    const innen = element();
    const buch = element();
    const zu: string[] = [];
    const ab1 = offenesFeld(() => [aussen], () => zu.push("aussen"));
    const ab2 = offenesFeld(() => [innen], () => {
      zu.push("innen");
      ab2();
    });
    druecke(aussen);
    expect(zu).toEqual(["innen"]);
    druecke(buch);
    expect(zu).toEqual(["innen", "aussen"]);
    ab1();
  });

  it("blättert nicht: der Druck und sein Klick erreichen das Buch nicht, ein Knopf daneben tut aber, was er soll", () => {
    const feld = element();
    const buch = element();
    const knopf = element("button");
    const imBuch: string[] = [];
    for (const art of ["pointerdown", "click"]) buch.addEventListener(art, () => imBuch.push(art));
    let geklickt = 0;
    knopf.addEventListener("click", () => geklickt++);
    let ab = offenesFeld(() => [feld], () => ab());
    druecke(buch);
    buch.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(imBuch).toEqual([]);
    buch.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(imBuch).toEqual(["click"]);
    ab = offenesFeld(() => [feld], () => ab());
    druecke(knopf);
    knopf.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(geklickt).toBe(1);
  });

  it("Esc schließt das zuletzt geöffnete", () => {
    const zu: string[] = [];
    const ab1 = offenesFeld(() => [], () => zu.push("eins"));
    const ab2 = offenesFeld(() => [], () => zu.push("zwei"));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(zu).toEqual(["zwei"]);
    ab2();
    ab1();
  });
});
