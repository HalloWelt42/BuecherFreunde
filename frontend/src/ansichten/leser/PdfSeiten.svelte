<script lang="ts">
  // Die Seiten eines PDF als Bild mit wählbarem Text: fortlaufend gescrollt oder Bogen für Bogen geblättert
  import { tick, untrack } from "svelte";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { blaettergesten } from "../../lib/leser/blaettergesten";
  import { PdfAnzeige } from "../../lib/leser/pdf/anzeige";
  import type { PdfBuch } from "../../lib/leser/pdf/dokument";
  import { Pdfmarkierungen } from "../../lib/leser/pdf/markierung";
  import { blattbreite } from "../../lib/leser/leseraum.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import { einpassen, geblaettert, nachbarn, sichtbareSeiten, type Ansicht, type Seitenrest } from "../../lib/leser/pdf/zoom";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { wischen } from "../../lib/leser/wischen";
  import { imBlick, Mitlauf, sichtVon } from "../../lib/leser/mitlauf";
  import type { Randeintrag } from "../../lib/leser/randmarken";
  import { vorgelesenIn } from "../../lib/leser/fokus";
  import type { Hilfeort } from "../../lib/leser/sitzung.svelte";

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
    /** Eine Seite ist samt Textebene gezeichnet */
    onbeschriftet: (nr: number) => void;
  }
  let { sitzung, pdf, ansicht, zoom, seite, fundstelle, fundseite, onseite, onmass, onrest, onbeschriftet }: Eigenschaften = $props();

  /** So viel der letzten Zeilen bleibt stehen, wenn eine hohe Seite in Abschnitten geblättert wird */
  const UEBERLAPP = 48;

  let flaeche: HTMLElement | undefined = $state();
  let anzeige: PdfAnzeige | null = null;
  let mitlauf: Mitlauf | null = null;
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
  /** Maß, mit dem die Seite in dieser Ansicht passt: in den freien Platz, höchstens so breit wie das Blatt (BF-36) */
  export function passend(fuer: Ansicht): number | null {
    return flaeche ? einpassen(fuer, pdf.mass, frei(), schale.telefon ? Infinity : blattbreite.wert) : null;
  }

  /** Wie weit die Seite oben schon durchgerollt ist, als Anteil ihrer Höhe */
  function durchgerollt(nr: number): number {
    const r = anzeige?.rahmen(nr)?.getBoundingClientRect();
    if (!flaeche || !r?.height) return 0;
    const oben = flaeche.getBoundingClientRect().top + punkte(getComputedStyle(flaeche).paddingTop);
    return Math.min(1, Math.max(0, (oben - r.top) / r.height));
  }

  async function rechne() {
    if (!anzeige) return;
    const mass = zoom ?? passend(ansicht) ?? anzeige.mass;
    // Ändert sich das Maß beim Rollen (Feld daneben, andere Breite), bleibt die Stelle in der Seite, wo sie war
    const anteil = blaettert ? 0 : durchgerollt(seite);
    Object.assign(anzeige, { mass, ansicht, seite });
    gezeigt = seite;
    onmass(mass);
    await tick();
    await anzeige.neu();
    const r = anteil && flaeche ? anzeige.rahmen(seite) : null;
    if (r && flaeche) flaeche.scrollTop += anteil * r.getBoundingClientRect().height;
    meldeRest();
  }

  // Markierungen und Fundstelle zeichengenau, je gezeichneter Seite (BF-38)
  const markierungen = new Pdfmarkierungen();

  function beschrifte(nr: number, ebene: HTMLElement) {
    const fund = markierungen.beschrifte(nr, ebene, sitzung.markierungen, nr === fundseite ? fundstelle : "");
    if (!fund || gerolltZurFundstelle || blaettert) return;
    gerolltZurFundstelle = true;
    fund.startContainer.parentElement?.scrollIntoView({ block: "nearest" });
  }

  function gezeichnet(nr: number, ebene: HTMLElement) {
    beschrifte(nr, ebene);
    onbeschriftet(nr);
  }

  export function zeichne() {
    anzeige?.zeichneErneut(beschrifte);
  }

  function gelesen(nr: number) {
    gezeigt = nr;
    onseite(nr);
  }

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    anzeige = new PdfAnzeige(pdf, f, { beiSeite: gelesen, gezeichnet });
    mitlauf = new Mitlauf({ get stand() { return f.scrollTop; }, set stand(w) { f.scrollTop = w; }, get hoehe() { const s = sichtVon(f); return s.unten - s.oben; } }, f);
    return () => {
      anzeige?.zerstoere();
      mitlauf?.zerstoere();
      markierungen.leere();
    };
  });

  // Ansicht, Zoom oder Breite des Blatts: neu rechnen, die Seite bleibt
  $effect(() => {
    void [ansicht, zoom, blattbreite.wert];
    untrack(() => void rechne());
  });

  // Sprung von außen
  $effect(() => {
    const ziel = seite;
    if (ziel !== gezeigt) untrack(() => void zeigeSeite(ziel, "oben"));
  });

  async function zeigeSeite(nr: number, kante: "oben" | "unten") {
    if (!anzeige) return;
    gezeigt = nr;
    if (!blaettert) return anzeige.zeige(nr);
    await tick();
    // Die vorab gezeichneten Seiten sind jetzt umgeordnet; ein verschobener Knoten nimmt jedem Bereich darin die Zeichen
    // (das DOM lässt Bereiche beim Herausnehmen zusammenfallen), darum ihre Markierungen und den Vorlesesatz neu legen
    anzeige.zeichneErneut(gezeichnet);
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
    void zeigeSeite(ziel, richtung > 0 ? "oben" : "unten");
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
    sitzung.bewegt();
  }

  // Für das Vorlesen: wo der Text einer Seite steht, die Seite zeigen, die gelesene Zeile im Blick halten
  export const wurzel = (nr: number): HTMLElement | null => anzeige?.rahmen(nr)?.querySelector<HTMLElement>(".textLayer") ?? null;

  function seiteImBlick(nr: number): boolean {
    if (blaettert) return bogen.includes(nr);
    const r = anzeige?.rahmen(nr)?.getBoundingClientRect();
    const s = flaeche && sichtVon(flaeche);
    return !!r && !!s && r.bottom > s.oben && r.top < s.unten;
  }

  export async function zeige(nr: number, bereich: Range | null, sofort: boolean): Promise<void> {
    if (!flaeche) return;
    if (!seiteImBlick(nr) || (blaettert && nr !== seite && !bogen.includes(nr))) {
      gezeigt = nr;
      onseite(nr);
      await zeigeSeite(nr, "oben");
      return;
    }
    if (!bereich) return;
    const r = bereich.getBoundingClientRect();
    const s = sichtVon(flaeche);
    mitlauf?.folge(r.top - s.oben, r.bottom - s.oben, sofort);
  }

  export function sichtbar(nr: number, bereich: Range | null): boolean {
    return bereich && flaeche ? imBlick(bereich, sichtVon(flaeche)) : seiteImBlick(nr);
  }

  export const hier = () => ({ seite, wortlaut: "" });

  // Für die Marken am Rand: Höhe einer Stelle auf einer sichtbaren Seite, rechte Kante des Blatts
  export function lage(nr: number, e: Randeintrag): number | null {
    const r = anzeige?.rahmen(nr);
    if (!flaeche || !r || !seiteImBlick(nr)) return null;
    const s = sichtVon(flaeche);
    if (e.art === "Markierung") {
      const q = markierungen.bereich((e.quelle as { id: number }).id)?.getBoundingClientRect();
      if (q && q.bottom > s.oben && q.top < s.unten) return q.top;
    }
    return Math.max(r.getBoundingClientRect().top + 16, s.oben);
  }

  // Für die Lesehilfen: ein PDF als Bild kennt keine Absätze, nur Zeilen
  export const hilfeort: Hilfeort = {
    blatt: () => anzeige?.rahmen(blaettert ? (bogen[0] ?? seite) : seite)?.getBoundingClientRect() ?? null,
    zeilenhoehe: () => 16 * (anzeige?.mass ?? 1),
    absatzBei: () => null,
    vorgelesen: () => vorgelesenIn(document, flaeche ?? null),
    mitAbsaetzen: false,
    rolle: (px) => {
      const vorher = flaeche!.scrollTop;
      flaeche!.scrollTop += px;
      return flaeche!.scrollTop !== vorher;
    },
    blaettere: () => {
      const vorher = [seite, flaeche?.scrollTop];
      vor();
      return seite !== vorher[0] || flaeche?.scrollTop !== vorher[1];
    },
    art: () => (blaettert ? "blaettern" : "scrollen"),
  };

  export function kante(): number | null {
    return anzeige?.rahmen(blaettert ? (bogen.at(-1) ?? seite) : seite)?.getBoundingClientRect().right ?? null;
  }
  export const seiten = (): number[] => (blaettert ? bogen : [seite]);

  const belegt = (p: { x: number; y: number }) => sitzung.belegt(p);

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
