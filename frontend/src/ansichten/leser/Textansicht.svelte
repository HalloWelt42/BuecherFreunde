<script lang="ts">
  // Seiten eines PDF als umfließender Text, mit Überschriften, Kästen und Abbildungen an ihrer Stelle
  import "../../stil/lesetext.css";
  import { onDestroy, tick, untrack } from "svelte";
  import { textBildUrl } from "../../lib/api/books";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { blaettergesten } from "../../lib/leser/blaettergesten";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import { Textfluss } from "../../lib/leser/fluss/textfluss";
  import { Textseiten, type Baustein } from "../../lib/leser/pdf/textseiten.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { zeichneMarkierungen, zeichneWortlaut } from "../../lib/leser/text/markierung";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Bildlupe from "./Bildlupe.svelte";

  interface Eigenschaften {
    sitzung: Lesesitzung;
    art: Leseart;
    startSeite: number;
    /** Wortlaut, der auf der Startseite gesucht wurde */
    fundstelle: string;
    grund: string;
    tinte: string;
    onstand: (stand: { seite: number; amAnfang: boolean; amEnde: boolean; innen: number }) => void;
    onoriginal: () => void;
    onmitte: () => void;
    belegt: () => boolean;
  }
  let { sitzung, art, startSeite, fundstelle, grund, tinte, onstand, onoriginal, onmitte, belegt }: Eigenschaften = $props();

  let flaeche: HTMLElement | undefined = $state();
  let blatt: HTMLElement | undefined = $state();
  let satz: HTMLElement | undefined = $state();
  let lupe = $state<{ quelle: string; beschreibung: string } | null>(null);
  let fluss: Textfluss | null = null;
  let gemeldet = 0;
  let gesucht = untrack(() => fundstelle);

  const text = new Textseiten(untrack(() => sitzung.buch.id), async (tun) => {
    const umbau = async () => {
      tun();
      await tick();
      zeichne();
    };
    if (fluss) await fluss.halte(umbau);
    else await umbau();
  });

  // Nachladen, bevor man an den Rand des Geladenen kommt. Vorn von selbst nur beim Blättern: ein Schwung mit dem Finger
  // stockte sonst, dort gibt es die Taste.
  const VORRAT = 2;
  async function fuelleNach() {
    if (!fluss) return;
    const hinten = fluss.danach < VORRAT && text.mitHinten;
    const vorn = !hinten && art === "blaettern" && fluss.davor < VORRAT && text.mitVorn;
    if (hinten ? await text.unten() : vorn && (await text.oben())) bewegt();
  }

  const seiteVon = (k: Node | undefined) => Number((k?.nodeType === Node.ELEMENT_NODE ? (k as Element) : k?.parentElement)?.closest<HTMLElement>("[data-textseite]")?.dataset.textseite) || 0;
  const abschnitt = (nr: number) => satz?.querySelector<HTMLElement>(`[data-textseite="${nr}"]`) ?? null;

  function bewegt() {
    if (!fluss) return;
    const nr = seiteVon(fluss.halt()?.knoten) || text.erste;
    gemeldet = nr;
    const amAnfang = fluss.amAnfang && text.erste === 1;
    const amEnde = fluss.amEnde && text.letzte >= text.gesamt;
    // Wie weit man in den geladenen Seiten ist, für einen Balken, der bei jedem Schirm vorrückt
    const geladen = text.letzte - text.erste + 1;
    const innen = amEnde ? 1 : Math.min(0.999, Math.max(0, fluss.anteil * geladen - (nr - text.erste)));
    onstand({ seite: nr, amAnfang, amEnde, innen });
    void fuelleNach();
  }

  async function beginne(ab: number) {
    if (!(await text.neu(ab))) return;
    await tick();
    if (!flaeche || !blatt || !satz) return;
    fluss ??= new Textfluss({ flaeche, blatt, satz }, art, bewegt);
    fluss.neu();
    springe(ab);
  }

  function springe(nr: number) {
    const a = abschnitt(nr);
    if (!a || !fluss) return;
    const treffer = gesucht && nr === startSeite ? zeichneWortlaut(a, gesucht) : null;
    if (treffer) gesucht = "";
    gemeldet = nr;
    fluss.zu(treffer ?? a);
  }

  // Sprung von außen (Seitenfeld, Verzeichnis): steht die Seite schon da, nur hin, sonst neu laden
  $effect(() => {
    const ziel = startSeite;
    if (!satz) return;
    untrack(() => {
      if (ziel === gemeldet) return;
      if (abschnitt(ziel)) springe(ziel);
      else void beginne(ziel);
    });
  });

  $effect(() => {
    const neu = art;
    untrack(() => {
      fluss?.setzeArt(neu);
      void fuelleNach();
    });
  });

  // Schrift, Zeilen, Rand: dieselbe Stelle bleibt
  $effect(() => {
    void [textansicht.groesse, textansicht.zeilen, textansicht.familie];
    untrack(() => void fluss?.halte(tick));
  });

  /** Einen Schirm weiter; am Rand des Geladenen erst nachholen */
  export async function vor() {
    if (fluss && !fluss.vor() && (await text.unten())) fluss.vor();
  }
  export async function zurueck() {
    if (fluss && !fluss.zurueck() && (await text.oben())) fluss.zurueck();
  }
  export function zeichne() {
    if (!satz) return;
    for (const s of satz.querySelectorAll<HTMLElement>("[data-textseite]")) zeichneMarkierungen(s, sitzung.markierungen.filter((m) => m.cfi_range === `page:${s.dataset.textseite}`));
  }

  $effect(() => {
    if (!flaeche) return;
    const griffe = { gilt: () => art === "blaettern", vor, zurueck, mitte: onmitte, belegt };
    return blaettergesten(flaeche, { rahmen: () => flaeche!.getBoundingClientRect() }, griffe);
  });

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    const beschreibe = (b: Range) => {
      const nr = seiteVon(b.startContainer) || gemeldet;
      return { cfi: `page:${nr}`, ort: schreibweise.seite(nr) };
    };
    return beobachteAuswahl(f, beschreibe, (a) => nimmAuswahl(sitzung, a) && getSelection()?.removeAllRanges());
  });

  onDestroy(() => fluss?.zerstoere());

  // Die Bildunterschrift gleich nach einer Abbildung beschreibt sie in der Lupe
  const beschreibung = (liste: Baustein[], n: number) => (liste[n + 1]?.art === "unterschrift" ? liste[n + 1].text : "");
</script>

{#snippet abbildung(nr: number, b: Baustein, worte: string)}
  {@const quelle = textBildUrl(sitzung.buch.id, nr, b.bild!)}
  <button type="button" class="abbildung" aria-label="Abbildung vergrößern" onclick={() => (lupe = { quelle, beschreibung: worte })}>
    <img src={quelle} alt={worte} loading="lazy" style:aspect-ratio={b.verhaeltnis ?? "auto"} style:--verhaeltnis={b.verhaeltnis ?? undefined} style:width={b.breite_em ? `${b.breite_em}em` : undefined} />
  </button>
{/snippet}

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="seiten lesetext textansicht rollen" lang="de" tabindex="0" role="document" aria-label="Text" bind:this={flaeche}>
  <article class="blatt" bind:this={blatt} style:--blattgrund={grund} style:--blatttinte={tinte} style:font-family={textansicht.familie} style:font-size="{(1.125 * textansicht.groesse) / 100}rem" style:line-height={textansicht.zeilen}>
    <div class="satz" bind:this={satz}>
      {#if text.mitVorn && art === "scrollen"}<div class="mitte frueher"><Knopf text="Frühere Seiten" symbol="arrow-up" klein laeuft={text.laedt} onclick={() => void text.oben()} /></div>{/if}
      {#if text.ohneText}
        <p>Diese Seiten sind Bilder ohne lesbaren Text, etwa eingescannt.</p>
        <div class="mitte"><Knopf text="Original" symbol="file-pdf" klein onclick={onoriginal} /></div>
      {/if}
      {#each text.seiten as s (s.nr)}
        <section data-textseite={s.nr}>
          <div class="seitenmarke">Seite {s.gedruckt || s.nr}</div>
          {#each s.bausteine as b, n (n)}
            {#if b.art === "ueberschrift"}<h2>{b.text}</h2>
            {:else if b.art === "unterschrift"}<p class="unterschrift">{b.text}</p>
            {:else if b.art === "bild"}{@render abbildung(s.nr, b, beschreibung(s.bausteine, n))}
            {:else if b.art === "kasten"}
              <aside class="kasten">
                {#if b.titel}<b>{b.titel}</b>{/if}
                {#each b.inhalt as t, j (j)}{#if t.art === "bild"}{@render abbildung(s.nr, t, "")}{:else}<p>{t.text}</p>{/if}{/each}
              </aside>
            {:else}<p>{b.text}</p>{/if}
          {/each}
        </section>
      {/each}
      {#if text.fehler}<p>Der Text ließ sich nicht laden: {text.fehler}</p><div class="mitte"><Knopf text="Erneut versuchen" symbol="rotate-right" klein onclick={() => void (text.seiten.length ? text.unten() : beginne(startSeite))} /></div>{/if}
      {#if text.gesamt > 0 && text.letzte >= text.gesamt}<div class="mitte ende">Ende</div>{:else if text.laedt && !text.seiten.length}<div class="mitte ende">Lädt</div>{/if}
    </div>
  </article>
</div>

{#if lupe}<Bildlupe {...lupe} onschliessen={() => (lupe = null)} />{/if}

<style>
  .mitte {
    display: flex;
    justify-content: center;
    padding: 0.5rem 0;
  }
  .ende {
    font-size: 0.8em;
    opacity: 0.7;
  }
  .seitenmarke {
    font-size: 0.75em;
    opacity: 0.65;
    text-align: center;
    padding: 1.25em 0 0.5em;
  }
  .satz h2 {
    font-family: inherit;
    margin: 1em 0 0.5em;
  }
  .unterschrift {
    font-size: 0.85em;
    opacity: 0.8;
  }
  .kasten {
    margin: 1em 0;
    padding: 0.75em 1em;
    border-radius: var(--r2);
    border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
    background: color-mix(in srgb, currentColor 6%, transparent);
  }
  .abbildung {
    display: block;
    margin: 1em auto;
    cursor: zoom-in;
  }
  .abbildung img {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 3px;
    background: #fff;
  }
  /* Geblättert passt jede Abbildung ganz auf einen Schirm, ohne weißen Rand daneben */
  :global(.schirmweise) .abbildung img {
    max-width: min(100%, calc((var(--satzhoehe) - 5em) * var(--verhaeltnis, 100)));
  }
</style>
