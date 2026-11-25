<script lang="ts">
  // Seiten eines PDF als umfließender Text, mit Überschriften, Kästen und Abbildungen an ihrer Stelle. Lädt ab der
  // gelesenen Seite in Ausschnitten nach (unten von selbst, oben auf Knopfdruck).
  import "@fontsource/atkinson-hyperlegible/400.css";
  import "@fontsource/atkinson-hyperlegible/400-italic.css";
  import "@fontsource/atkinson-hyperlegible/700.css";
  import { untrack } from "svelte";
  import { textBildUrl, textSeiten } from "../../lib/api/books";
  import { vorgabeThema } from "../../lib/leser/darstellung";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { darstellung } from "../../lib/stand/darstellung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Bildlupe from "./Bildlupe.svelte";

  interface Baustein {
    art: "ueberschrift" | "absatz" | "unterschrift" | "bild" | "kasten";
    text: string;
    titel: string;
    inhalt: Baustein[];
    bild: number | null;
    verhaeltnis: number | null;
    breite_em: number | null;
  }
  interface Textseite {
    nr: number;
    gedruckt: string | null;
    bausteine: Baustein[];
  }

  let { buch, startSeite, onseite, onoriginal }: { buch: BuchEinzeln; startSeite: number; onseite: (nr: number) => void; onoriginal: () => void } = $props();

  const AUSSCHNITT = 6;
  let seiten = $state.raw<Textseite[]>([]);
  let gesamt = $state(0);
  let laedt = $state(false);
  let fehler = $state("");
  let flaeche: HTMLElement | undefined = $state();
  let ende: HTMLElement | undefined = $state();
  let lupe = $state<{ quelle: string; beschreibung: string } | null>(null);
  let gemeldet = 0;

  let erste = $derived(seiten[0]?.nr ?? 1);
  let letzte = $derived(seiten.at(-1)?.nr ?? 0);
  let ohneText = $derived(seiten.length > 0 && seiten.every((s) => s.bausteine.length === 0));
  let thema = $derived(textansicht.thema(vorgabeThema(darstellung.dunkel)));

  async function lade(ab: number, art: "neu" | "unten" | "oben") {
    if (laedt) return;
    laedt = true;
    fehler = "";
    try {
      const antwort = await textSeiten(buch.id, ab, AUSSCHNITT);
      gesamt = antwort.gesamt;
      const neue: Textseite[] = antwort.seiten;
      if (art === "neu") {
        seiten = neue;
        gemeldet = ab;
        requestAnimationFrame(() => flaeche && (flaeche.scrollTop = 0));
      } else if (art === "unten") seiten = [...seiten, ...neue.filter((s) => s.nr > letzte)];
      else {
        // Vorn einfügen, ohne dass der Text unter dem Finger springt
        const vorher = flaeche?.scrollHeight ?? 0;
        seiten = [...neue.filter((s) => s.nr < erste), ...seiten];
        requestAnimationFrame(() => flaeche && (flaeche.scrollTop += flaeche.scrollHeight - vorher));
      }
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      laedt = false;
    }
  }

  // Sprung von außen (Seitenfeld, Verzeichnis): steht die Seite schon da, nur hinrollen, sonst neu laden
  $effect(() => {
    const ziel = startSeite;
    untrack(() => {
      if (ziel === gemeldet) return;
      const da = flaeche?.querySelector<HTMLElement>(`[data-textseite="${ziel}"]`);
      if (da && flaeche) {
        gemeldet = ziel;
        flaeche.scrollTop += da.getBoundingClientRect().top - flaeche.getBoundingClientRect().top - 72;
      } else void lade(ziel, "neu");
    });
  });

  $effect(() => {
    if (!ende || !flaeche) return;
    const beobachter = new IntersectionObserver((e) => {
      if (e[0].isIntersecting && letzte > 0 && letzte < gesamt) void lade(letzte + 1, "unten");
    }, { root: flaeche, rootMargin: "800px 0px" });
    beobachter.observe(ende);
    return () => beobachter.disconnect();
  });

  function gerollt() {
    if (!flaeche) return;
    const kante = flaeche.getBoundingClientRect().top + 110;
    let jetzt = erste;
    for (const el of flaeche.querySelectorAll<HTMLElement>("[data-textseite]")) {
      if (el.getBoundingClientRect().top > kante) break;
      jetzt = Number(el.dataset.textseite);
    }
    if (jetzt === gemeldet) return;
    gemeldet = jetzt;
    onseite(jetzt);
  }

  // Die Bildunterschrift gleich nach einer Abbildung beschreibt sie in der Lupe
  const beschreibung = (liste: Baustein[], n: number) => (liste[n + 1]?.art === "unterschrift" ? liste[n + 1].text : "");
</script>

{#snippet abbildung(nr: number, b: Baustein, text: string)}
  {@const quelle = textBildUrl(buch.id, nr, b.bild!)}
  <button type="button" class="abbildung" aria-label="Abbildung vergrößern" onclick={() => (lupe = { quelle, beschreibung: text })}>
    <img src={quelle} alt={text} loading="lazy" style:aspect-ratio={b.verhaeltnis ?? "auto"} style:width={b.breite_em ? `${b.breite_em}em` : undefined} />
  </button>
{/snippet}

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="seiten textansicht rollen" lang="de" tabindex="0" role="document" aria-label="Text" bind:this={flaeche} onscroll={gerollt}>
  <article class="blatt" style:background={thema.bg} style:color={thema.fg} style:font-family={textansicht.familie} style:font-size="{1.125 * textansicht.groesse / 100}rem" style:line-height={textansicht.zeilen}>
    {#if erste > 1}<div class="mitte"><Knopf text="Frühere Seiten" symbol="arrow-up" klein laeuft={laedt} onclick={() => void lade(Math.max(1, erste - AUSSCHNITT), "oben")} /></div>{/if}
    {#if ohneText}
      <p>Diese Seiten sind Bilder ohne lesbaren Text, etwa eingescannt. Als Text gibt es hier nichts zu lesen.</p>
      <div class="mitte"><Knopf text="Zur Originalansicht" symbol="file-pdf" klein onclick={onoriginal} /></div>
    {/if}
    {#each seiten as s (s.nr)}
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
    {#if fehler}<p>Der Text ließ sich nicht laden: {fehler}</p><div class="mitte"><Knopf text="Erneut versuchen" symbol="rotate-right" klein onclick={() => void lade(letzte + 1 || startSeite, seiten.length ? "unten" : "neu")} /></div>{/if}
    <div class="mitte ende" bind:this={ende}>{#if laedt}Lädt{:else if gesamt > 0 && letzte >= gesamt}Ende des Buchs{/if}</div>
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
  .blatt h2 {
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
</style>
