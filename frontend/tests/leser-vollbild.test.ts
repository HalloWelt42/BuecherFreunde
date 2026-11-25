import { blattrand } from "../src/lib/leser/blattrand.svelte";
import { zeigeBlattgrund } from "../src/lib/stand/blattgrund";

describe("Vollbild", () => {
  it("färbt Statusleiste und Grund und stellt beides wieder her", () => {
    document.head.innerHTML = '<meta name="theme-color" content="#0b1312">';
    document.body.style.background = "";
    const zurueck = zeigeBlattgrund("#f4ecd8");
    const meta = document.querySelector<HTMLMetaElement>("meta")!;
    expect([meta.content, document.body.style.background]).toEqual(["#f4ecd8", "rgb(244, 236, 216)"]);
    zurueck();
    expect([meta.content, document.body.style.background, document.documentElement.style.background]).toEqual(["#0b1312", "", ""]);
  });

  it("hält oben Platz für das Zeichen, auch ohne Rand", () => {
    blattrand.wert = 0;
    expect([blattrand.wert, blattrand.oben(false), blattrand.oben(true)]).toEqual([0, 0, 28]);
    blattrand.wert = 61;
    expect([blattrand.wert, blattrand.oben(true), localStorage.getItem("leser.rand")]).toEqual([60, 60, "60"]);
    blattrand.wert = 500;
    expect(blattrand.wert).toBe(blattrand.bereich.max);
  });
});
