<script lang="ts">
  // Bunte Marken am Rand des Blatts (Entwurf scratchpad/marken.png): breit für die offene Seite auf Höhe ihrer Stelle, schmal für
  // alle anderen an festem Platz. Am Telefon nur schmale Streifen, die kein Wischen und keine Auswahl blockieren.
  import { legeRand, randeintraege, schriftAuf, type Gelegt, type Randeintrag } from "../../lib/leser/randmarken";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import type { Aufteilung } from "../../lib/leser/leseraum.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import type { Markierung } from "../../lib/typen";

  let { sitzung, rahmen, raum, feld }: { sitzung: Lesesitzung; rahmen: HTMLElement; raum: Aufteilung; feld?: HTMLElement } = $props();

  const MASS = { rechner: { fern: [15, 26], hier: [34, 46] }, telefon: { fern: [6, 30], hier: [6, 64] } };
  const ABSTAND = 4;
  /** So breit ist am Telefon die Fläche, die das Tippen auf einen Streifen fängt */
  const TIPPZONE = 44;

  let eintraege = $derived(randeintraege(sitzung.markierungen, sitzung.notizen, sitzung.etiketten));
  let telefon = $derived(schale.telefon);
  let mass = $derived(telefon ? MASS.telefon : MASS.rechner);
  let lage = $state<{ links: number; grenze: number; hier: Gelegt<Randeintrag>[]; fern: Gelegt<Randeintrag>[] }>({ links: 0, grenze: 0, hier: [], fern: [] });
  /** Rechts neben der Marke ist kein Platz für die Karte (Kante der Bühne oder das Feld daneben): sie klappt nach links */
  let nachLinks = $derived(lage.links + 240 > lage.grenze);
  let offen = $state("");
  let bild = 0;

  // Der freie Bereich zwischen den Leisten, im Rahmen gemessen
  function bereich(r: DOMRect): { oben: number; unten: number } {
    const oben = rahmen.querySelector(".leseleiste.oben")?.getBoundingClientRect();
    const unten = rahmen.querySelector(".leseleiste.unten")?.getBoundingClientRect();
    return { oben: (oben ? oben.bottom - r.top : 0) + 8, unten: (unten ? unten.top - r.top : r.height) - 8 };
  }

  function lege() {
    const ort = sitzung.rand;
    if (!ort) return;
    const r = rahmen.getBoundingClientRect();
    const { oben, unten } = bereich(r);
    const hier: { y: number; eintrag: Randeintrag }[] = [];
    const fern: { anteil: number; eintrag: Randeintrag }[] = [];
    for (const e of eintraege) {
      const y = ort.lage(e);
      if (y !== null) hier.push({ y: y - r.top, eintrag: e });
      else {
        const a = ort.anteil(e);
        if (a !== null) fern.push({ anteil: a, eintrag: e });
      }
    }
    const kante = ort.kante();
    const breite = mass.hier[0];
    // Am Rechner stehen sie im eigenen Rand rechts neben dem Blatt, nie unter dem Feld daneben (lib/leser/leseraum.svelte.ts)
    const rechtsBis = r.width - (raum.rechts - raum.markenrand);
    const links = telefon ? r.width - mass.hier[0] : kante === null ? rechtsBis - breite - 2 : Math.min(kante - r.left, rechtsBis - breite - 2);
    const grenze = feld ? feld.getBoundingClientRect().left - r.left - 8 : r.width;
    lage = { links, grenze, ...legeRand(hier, fern, { oben, unten, breit: mass.hier[1], schmal: mass.fern[1], abstand: ABSTAND }) };
  }

  // Bei jeder Bewegung der Ansicht, neuen Einträgen und anderer Größe neu legen, einmal je Bild
  $effect(() => {
    void [sitzung.bewegung, eintraege, telefon, sitzung.rand, schale.vollbild, sitzung.feld, raum, feld];
    cancelAnimationFrame(bild);
    bild = requestAnimationFrame(lege);
  });
  $effect(() => {
    const beobachter = new ResizeObserver(() => {
      cancelAnimationFrame(bild);
      bild = requestAnimationFrame(lege);
    });
    beobachter.observe(rahmen);
    return () => {
      beobachter.disconnect();
      cancelAnimationFrame(bild);
    };
  });

  function springe(e: Randeintrag) {
    offen = "";
    const g = sitzung.griffe;
    if (e.art === "Markierung") g?.zurMarkierung(e.quelle as Markierung);
    else g?.zurStelle(e.seite ? `S.${e.seite}` : e.ort, e.cfi, e.prozent ?? 0);
  }

  /** Erstes Tippen klappt auf, das zweite öffnet zum Bearbeiten; schmale springen gleich */
  function tippe(g: Gelegt<Randeintrag>, nah: boolean) {
    const e = g.eintraege[0];
    if (!nah) return springe(e);
    if (offen !== e.schluessel) offen = e.schluessel;
    else {
      offen = "";
      sitzung.feld = "stellen";
    }
  }

  // Am Telefon fangen unsichtbare Flächen das Tippen, nur genau dort; Wischen und Auswählen gehen durch
  $effect(() => {
    if (!telefon) {
      sitzung.randtreffer = null;
      return;
    }
    sitzung.randtreffer = (x, y) => {
      const r = rahmen.getBoundingClientRect();
      if (x < r.right - TIPPZONE || x > r.right) return false;
      const treffer = (liste: Gelegt<Randeintrag>[], h: number) => liste.find((g) => y >= r.top + g.y - 7 && y <= r.top + g.y + h + 7);
      const nah = treffer(lage.hier, mass.hier[1]);
      const fern = !nah && treffer(lage.fern, mass.fern[1]);
      if (nah) tippe(nah, true);
      else if (fern) tippe(fern, false);
      else if (offen) offen = "";
      else return false;
      return true;
    };
    return () => (sitzung.randtreffer = null);
  });

  const titel = (g: Gelegt<Randeintrag>) => (g.eintraege.length > 1 ? `${g.eintraege.length} Einträge, ab ${g.eintraege[0].ort}` : `${g.eintraege[0].art}, ${g.eintraege[0].ort}: ${g.eintraege[0].text.slice(0, 80)}`);
</script>

<div class="randmarken" class:telefon aria-label="Marken am Rand" role="group" style:--links="{lage.links}px">
  {#each lage.fern as g (g.eintraege[0].schluessel)}
    {@const e = g.eintraege[0]}
    <button type="button" class="randmarke fern" style:top="{g.y}px" style:--f={e.farbe} style:--auf={schriftAuf(e.farbe)} title={titel(g)} aria-label="{titel(g)}, hinspringen" tabindex={telefon ? -1 : 0} onclick={() => tippe(g, false)}>{#if g.eintraege.length > 1 && !telefon}<span class:laengs={g.eintraege.length >= 100} class:eng={g.eintraege.length >= 10000}>{g.eintraege.length}</span>{/if}</button>
  {/each}
  {#each lage.hier as g, n (g.eintraege[0].schluessel)}
    {@const e = g.eintraege[0]}
    <button type="button" class="randmarke hier" class:auf={offen === e.schluessel} style:top="{g.y}px" style:--f={e.farbe} style:--auf={schriftAuf(e.farbe)} aria-label={titel(g)} aria-expanded={offen === e.schluessel} tabindex={telefon ? -1 : 0} onclick={() => tippe(g, true)}>
      {#if !telefon}<span class="nummer">{g.eintraege.length > 1 ? `${n + 1}+` : n + 1}</span>{/if}
    </button>
    <div class="randkarte" class:nach-links={nachLinks} class:auf={offen === e.schluessel} style:top="{g.y}px" style:--f={e.farbe} style:--auf={schriftAuf(e.farbe)} role="note">
      <span class="text">{e.text}</span>
      <small>{e.art}, {e.ort}{g.eintraege.length > 1 ? `, und ${g.eintraege.length - 1} weitere` : ""}</small>
    </div>
  {/each}
</div>

<style>
  .randmarken {
    position: absolute;
    inset: 0;
    z-index: 4;
    pointer-events: none;
  }
  .randmarke {
    position: absolute;
    left: var(--links);
    display: grid;
    place-items: center;
    background: var(--f);
    color: var(--auf);
    font-size: 0.8125rem;
    font-weight: 600;
    border-radius: 0 5px 5px 0;
    box-shadow: 1px 1px 3px rgb(0 0 0 / 0.4);
    pointer-events: auto;
    cursor: pointer;
  }
  .fern {
    width: 15px;
    height: 26px;
    opacity: 0.95;
  }
  /* Die Marke wächst nicht mit der Schrift, ihre Zahl darum auch nicht: sie passt immer hinein. Ab drei Stellen steht sie
     längs, ab fünf kleiner */
  .fern span {
    font-size: min(0.6875rem, 11px);
    line-height: 1;
  }
  .fern span.laengs {
    writing-mode: vertical-rl;
  }
  .fern span.eng {
    font-size: 8px;
  }
  .hier {
    width: 34px;
    height: 46px;
    border-radius: 0 6px 6px 0;
  }
  .randkarte {
    position: absolute;
    left: var(--links);
    z-index: 5;
    max-width: 14rem;
    padding: 0.5625rem 0.8125rem;
    border-radius: 0 6px 6px 0;
    background: var(--f);
    color: var(--auf);
    font-size: 0.875rem;
    line-height: 1.3;
    box-shadow: 1px 1px 3px rgb(0 0 0 / 0.4);
    visibility: hidden;
    pointer-events: none;
  }
  .randkarte .text {
    display: -webkit-box;
    -webkit-line-clamp: 6;
    line-clamp: 6;
    -webkit-box-orient: vertical;
    overflow: hidden;
    overflow-wrap: anywhere;
  }
  .randkarte small {
    display: block;
    margin-top: 0.1875rem;
    font-size: 0.75rem;
    opacity: 0.75;
  }
  .hier:hover + .randkarte,
  .hier:focus-visible + .randkarte,
  .randkarte.auf {
    visibility: visible;
  }
  .randkarte.nach-links {
    left: auto;
    right: calc(100% - var(--links) + 4px);
    border-radius: 6px;
  }
  /* Telefon: sechs Pixel am Rand, die Karte klappt nach links auf */
  .telefon .randmarke {
    width: 6px;
    border-radius: 3px 0 0 3px;
    box-shadow: none;
    pointer-events: none;
  }
  .telefon .fern {
    height: 30px;
  }
  .telefon .hier {
    height: 64px;
  }
  .telefon .randkarte {
    left: auto;
    right: 10px;
    max-width: min(15rem, calc(100% - 3rem));
    border-radius: 6px;
    font-size: 0.9375rem;
  }
</style>
