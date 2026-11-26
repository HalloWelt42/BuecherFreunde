<script lang="ts">
  // Gezeichneter Umschlag für Bücher ohne Bild; die Farben hängen fest am Buch
  import { VORGABE } from "../palette";
  let { buch }: { buch: { id: number; title: string; author?: string } } = $props();

  const HOEHE = 290;
  let farben = $derived(VORGABE[buch.id % VORGABE.length]);

  // Breite in Schriftgraden: Zeichen in voller Breite (Chinesisch, Japanisch, Koreanisch) zählen ganz, die übrigen 0,6
  const BREIT = /[\u1100-\u115F\u2E80-\uA4CF\uAC00-\uD7A3\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFF60\uFFE0-\uFFE6]/u;
  const ZEILE = 14 * 0.6;
  const graphem = typeof Intl !== "undefined" && "Segmenter" in Intl ? new Intl.Segmenter("de", { granularity: "grapheme" }) : null;
  const zeichen = (text: string): string[] => (graphem ? [...graphem.segment(text)].map((t) => t.segment) : [...text]);
  const breite = (text: string): number => zeichen(text).reduce((summe, z) => summe + (BREIT.test(z) ? 1 : 0.6), 0);

  /** Ein Wort breiter als eine Zeile bricht um, mit Trennstrich, wo man ihn setzt; sonst würde die Schrift unlesbar klein */
  function teile(wort: string): string[] {
    if (breite(wort) <= ZEILE) return [wort];
    const stuecke: string[] = [];
    let jetzt = "";
    for (const z of zeichen(wort)) {
      if (jetzt && breite(jetzt + z) > ZEILE - 0.6) {
        stuecke.push(BREIT.test(z) ? jetzt : `${jetzt}-`);
        jetzt = "";
      }
      jetzt += z;
    }
    return [...stuecke, jetzt];
  }

  function umbrechen(text: string): string[] {
    const zeilen: string[] = [];
    for (const wort of text.split(/\s+/).filter(Boolean).flatMap(teile)) {
      const letzte = zeilen[zeilen.length - 1];
      if (letzte !== undefined && breite(`${letzte} ${wort}`) <= ZEILE) zeilen[zeilen.length - 1] = `${letzte} ${wort}`;
      else zeilen.push(wort);
    }
    return zeilen;
  }

  let zeilen = $derived.by(() => {
    const alle = umbrechen((buch.title ?? "").trim() || "Ohne Titel");
    return alle.length > 6 ? [...alle.slice(0, 5), `${alle[5]} ...`] : alle;
  });
  let grad = $derived(Math.min(27, 164 / Math.max(...zeilen.map(breite))));
</script>

<svg viewBox="0 0 200 {HOEHE}" aria-hidden="true">
  <rect width="200" height={HOEHE} fill={farben[0]} />
  <rect x="18" y="30" width="46" height="7" fill={farben[1]} />
  {#each zeilen as zeile, n (n)}<text x="18" y={72 + n * grad * 1.13} class="t" font-size={grad} fill={farben[2]}>{zeile}</text>{/each}
  <text x="18" y={HOEHE - 20} class="a" fill={farben[2]}>{(buch.author ?? "").slice(0, 28)}</text>
</svg>

<style>
  .t {
    font-family: var(--buchschrift);
    font-weight: 700;
  }
  .a {
    font: 600 12px var(--schrift);
  }
</style>
