<script lang="ts">
  // Die Seiten eines PDF als Bild mit wählbarem Text: fortlaufend gescrollt oder Bogen für Bogen geblättert
  import { tick, untrack } from "svelte";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { blaettergesten } from "../../lib/leser/blaettergesten";
  import { PdfAnzeige } from "../../lib/leser/pdf/anzeige";
  import type { PdfBuch } from "../../lib/leser/pdf/dokument";
  import { leereEbene, zeichneFundstelle, zeichneMarkierungen } from "../../lib/leser/pdf/markierung";
  import { einpassen, geblaettert, nachbarn, sichtbareSeiten, type Ansicht, type Seitenrest } from "../../lib/leser/pdf/zoom";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { wischen } from "../../lib/leser/wischen";

  interface Eigenschaften {
    sitzung: Lesesitzung;
    pdf: PdfBuch;
    ansicht: Ansicht;
    /** Maß von Hand; null passt die Seite ein */
    zoom: number | null;
    seite: number;
    fundstelle: string;
    fundseite: number;
    onseite: (nr: number) => void;
    onmass: (mass: number) => void;
    onrest: (rest: Seitenrest) => void;
  }
  let { sitzung, pdf, ansicht, zoom, seite, fundstelle, fundseite, onseite, onmass, onrest }: Eigenschaften = $props();

  /** So viel der letzten Zeilen bleibt stehen, wenn eine hohe Seite in Abschnitten geblättert wird */
  const UEBERLAPP = 48;

  let flaeche: HTMLElement | undefined = $state();
  let anzeige: PdfAnzeige | null = null;
  let gezeigt = untrack(() => seite);
  let gerolltZurFundstelle = false;

  let blaettert = $derived(geblaettert(ansicht));
  let bogen = $derived(blaettert ? sichtbareSeiten(ansicht, seite, pdf.seiten) : []);
  // Die Nachbarn stehen fertig bereit, unsichtbar: ein Schritt zeigt sie ohne Aufblitzen
  let boegen = $derived(blaettert ? [bogen, ...nachbarn(ansicht, seite, pdf.seiten)] : []);

  const punkte = (wert: string) => Number.parseFloat(wert) || 0;
  function frei() {
    const s = getComputedStyle(flaeche!);
    return { breite: flaeche!.clientWidth - punkte(s.paddingLeft) - punkte(s.paddingRight), hoehe: flaeche!.clientHeight - punkte(s.paddingTop) - punkte(s.paddingBottom) };
  }
  /** Maß, mit dem die Seite in dieser Ansicht passt */
  export function passend(fuer: Ansicht): number | null {
    return flaeche ? einpassen(fuer, pdf.mass, frei()) : null;
  }

  async function rechne() {
    if (!anzeige) return;
    const mass = zoom ?? passend(ansicht) ?? anzeige.mass;
    Object.assign(anzeige, { mass, ansicht, seite });
    gezeigt = seite;
    onmass(mass);
    await tick();
    await anzeige.neu();
    meldeRest();
  }

  function beschrifte(nr: number, ebene: HTMLElement) {
    zeichneMarkierungen(ebene, nr, sitzung.markierungen);
    if (!fundstelle || nr !== fundseite) return;
    const erstes = zeichneFundstelle(ebene, fundstelle);
    if (!erstes || gerolltZurFundstelle || blaettert) return;
    gerolltZurFundstelle = true;
    erstes.scrollIntoView({ block: "nearest" });
  }

  export function zeichne() {
    anzeige?.zeichneErneut((nr, ebene) => {
      leereEbene(ebene);
      beschrifte(nr, ebene);
    });
  }

  function gelesen(nr: number) {
    gezeigt = nr;
    onseite(nr);
  }

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    anzeige = new PdfAnzeige(pdf, f, { beiSeite: gelesen, gezeichnet: beschrifte });
    return () => anzeige?.zerstoere();
  });

  // Ansicht oder Zoom: neu rechnen, die Seite bleibt
  $effect(() => {
    void [ansicht, zoom];
    untrack(() => void rechne());
  });

  // Sprung von außen
  $effect(() => {
    const ziel = seite;
    if (ziel !== gezeigt) untrack(() => void zeige(ziel, "oben"));
  });

  async function zeige(nr: number, kante: "oben" | "unten") {
    if (!anzeige) return;
    gezeigt = nr;
    if (!blaettert) return anzeige.zeige(nr);
    await tick();
    if (flaeche) flaeche.scrollTop = kante === "oben" ? 0 : flaeche.scrollHeight;
    void anzeige.blaettere(nr);
    meldeRest();
  }

  export const vor = () => schritt(1);
  export const zurueck = () => schritt(-1);

  function schritt(richtung: 1 | -1) {
    if (blaettert && rollt(richtung)) {
      flaeche!.scrollTop += richtung * Math.max(80, frei().hoehe - UEBERLAPP);
      return;
    }
    const weite = ansicht === "doppel" ? 2 : 1;
    const ziel = Math.min(pdf.seiten, Math.max(1, seite + richtung * weite));
    if (ziel === seite) return;
    gezeigt = ziel;
    onseite(ziel);
    void zeige(ziel, richtung > 0 ? "oben" : "unten");
  }

  // Eine vergrößerte oder im Querformat hohe Seite schiebt erst selbst
  function rollt(richtung: 1 | -1): boolean {
    const f = flaeche!;
    return richtung > 0 ? f.scrollTop < f.scrollHeight - f.clientHeight - 2 : f.scrollTop > 2;
  }
  function schiebt(achse: "x" | "y", richtung: 1 | -1): boolean {
    if (achse === "y") return rollt(richtung);
    const f = flaeche!;
    return richtung > 0 ? f.scrollLeft < f.scrollWidth - f.clientWidth - 2 : f.scrollLeft > 2;
  }

  function meldeRest() {
    if (flaeche) onrest({ oben: blaettert && rollt(-1), unten: blaettert && rollt(1) });
  }

  function gerollt() {
    anzeige?.gerollt();
    if (blaettert) meldeRest();
  }

  const belegt = () => sitzung.belegt();

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    if (blaettert) return blaettergesten(f, { rahmen: () => f.getBoundingClientRect() }, { gilt: () => true, vor, zurueck, mitte: () => sitzung.tippeMitte(), belegt, schiebt });
    // Fortlaufend und eingepasst: waagrecht wischen springt eine Seite
    if (ansicht !== "scroll") return wischen(f, { links: vor, rechts: zurueck });
  });

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    const seiteVon = (b: Range) => Number((b.startContainer.parentElement?.closest("[data-seite]") as HTMLElement | null)?.dataset.seite) || seite;
    return beobachteAuswahl(f, (b) => ({ cfi: `page:${seiteVon(b)}`, ort: schreibweise.seite(seiteVon(b)) }), (a) => nimmAuswahl(sitzung, a) && getSelection()?.removeAllRanges());
  });

  // Die Größe der Fläche ändert sich: eingepasste Ansichten neu rechnen
  $effect(() => {
    const f = flaeche;
    if (!f) return;
    // Der freie Platz zählt: im Vollbild fällt nur der Rand weg, die Fläche selbst kann gleich bleiben
    const mass = () => frei().breite + frei().hoehe;
    let zuvor = mass();
    const beobachter = new ResizeObserver(() => {
      const jetzt = mass();
      if (jetzt === zuvor || f.clientWidth === 0) return;
      zuvor = jetzt;
      if (zoom === null) void rechne();
      else meldeRest();
    });
    beobachter.observe(f);
    return () => beobachter.disconnect();
  });
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="seiten pdf rollen" class:blaettert tabindex="0" role="document" aria-label="Seiten" bind:this={flaeche} onscroll={gerollt}>
  {#if blaettert}
    {#each boegen as b (b[0])}
      <div class="bogen" class:wartet={b[0] !== bogen[0]}>{#each b as nr (nr)}<div class="pdfseite" data-seite={nr}><span class="nummer">{nr}</span></div>{/each}</div>
    {/each}
  {:else}
    {#each { length: pdf.seiten } as _, n (n)}<div class="pdfseite" data-seite={n + 1}><span class="nummer">{n + 1}</span></div>{/each}
  {/if}
</div>
