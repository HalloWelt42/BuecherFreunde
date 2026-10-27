<script>
  // Textansicht eines PDF: die Seiten als umfließende Absätze statt fester Zeilen. Lädt ab der aktuellen Seite in
  // Ausschnitten nach (unten von selbst, oben auf Knopfdruck) und meldet die oberste sichtbare Seite als Leseposition.
  import { untrack } from "svelte";
  import { textSeiten } from "../api/books.js";
  import { textansicht } from "./textansicht.svelte.js";

  let { bookId, startSeite = 1, onSeite = () => {}, onOriginal = () => {} } = $props();

  const AUSSCHNITT = 10;

  let seiten = $state([]);
  let gesamt = $state(0);
  let laedt = $state(false);
  let fehler = $state("");
  let flaeche = $state(null);
  let ende = $state(null);

  let erste = $derived(seiten[0]?.nr ?? 1);
  let letzte = $derived(seiten.at(-1)?.nr ?? 0);
  let ohneText = $derived(seiten.length > 0 && seiten.every((s) => s.absaetze.length === 0));

  async function lade(ab, vorne) {
    if (laedt) return;
    laedt = true;
    fehler = "";
    try {
      const antwort = await textSeiten(bookId, ab, AUSSCHNITT);
      gesamt = antwort.gesamt;
      if (!vorne) {
        seiten = [...seiten, ...antwort.seiten];
        return;
      }
      // Vorn einfügen, ohne dass der Text unter dem Finger springt
      const hoeheVorher = flaeche.scrollHeight;
      seiten = [...antwort.seiten.filter((s) => s.nr < erste), ...seiten];
      requestAnimationFrame(() => { flaeche.scrollTop += flaeche.scrollHeight - hoeheVorher; });
    } catch (e) {
      fehler = e.message;
    } finally {
      laedt = false;
    }
  }

  lade(untrack(() => startSeite), false);

  // Unten angekommen: nächsten Ausschnitt laden
  $effect(() => {
    if (!ende || !flaeche) return;
    const beobachter = new IntersectionObserver((eintraege) => {
      if (eintraege[0].isIntersecting && letzte > 0 && letzte < gesamt) lade(letzte + 1, false);
    }, { root: flaeche, rootMargin: "600px 0px" });
    beobachter.observe(ende);
    return () => beobachter.disconnect();
  });

  // Oberste sichtbare Seite melden
  let gemeldet = 0;
  function rollen() {
    const oben = flaeche.getBoundingClientRect().top;
    let aktuell = erste;
    for (const el of flaeche.querySelectorAll("[data-seite]")) {
      if (el.getBoundingClientRect().top - oben > 40) break;
      aktuell = Number(el.dataset.seite);
    }
    if (aktuell !== gemeldet) {
      gemeldet = aktuell;
      onSeite(aktuell);
    }
  }
</script>

<div
  class="textansicht"
  lang="de"
  bind:this={flaeche}
  onscroll={rollen}
  style:background-color={textansicht.thema.bg}
  style:color={textansicht.thema.fg}
  style:--schrift="{textansicht.schrift}%"
>
  <div class="spalte">
    {#if erste > 1}
      <button class="frueher" disabled={laedt} onclick={() => lade(Math.max(1, erste - AUSSCHNITT), true)}>
        Frühere Seiten
      </button>
    {/if}

    {#if ohneText}
      <div class="hinweis">
        <p>Diese Seiten haben keine Textschicht (eingescannt), daher gibt es hier keinen Fließtext.</p>
        <button onclick={onOriginal}>Zur Originalansicht</button>
      </div>
    {/if}

    {#each seiten as seite (seite.nr)}
      <section data-seite={seite.nr}>
        <div class="seitenmarke">Seite {seite.gedruckt || seite.nr}</div>
        {#each seite.absaetze as absatz, i (i)}
          <p>{absatz}</p>
        {/each}
      </section>
    {/each}

    {#if fehler}
      <p class="hinweis">Text konnte nicht geladen werden: {fehler}</p>
    {/if}
    <div class="ende" bind:this={ende}>
      {#if laedt}Lädt ...{:else if letzte >= gesamt && gesamt > 0}Ende des Buchs{/if}
    </div>
  </div>
</div>

<style>
  .textansicht {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: clip;
    transition: background-color 0.2s, color 0.2s;
  }

  .spalte {
    max-width: 40em;
    margin: 0 auto;
    padding: 1rem 1.25rem 3rem;
    font-family: Georgia, "Times New Roman", serif;
    font-size: calc(18px * var(--schrift) / 100);
    line-height: 1.6;
  }

  p {
    margin: 0 0 0.9em;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    overflow-wrap: anywhere;
  }

  .seitenmarke {
    margin: 1.25rem 0 0.75rem;
    font-family: var(--font-sans);
    font-size: 13px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    opacity: 0.55;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .seitenmarke::after {
    content: "";
    flex: 1;
    border-top: 1px solid currentColor;
    opacity: 0.4;
  }

  .frueher,
  .hinweis button {
    display: block;
    width: 100%;
    height: 44px;
    margin: 0.25rem 0 0.5rem;
    border: 1px solid currentColor;
    border-radius: 10px;
    background: none;
    color: inherit;
    font-family: var(--font-sans);
    font-size: 16px;
    opacity: 0.8;
  }

  .hinweis {
    font-family: var(--font-sans);
    font-size: 16px;
    margin: 1rem 0;
  }

  .ende {
    min-height: 3rem;
    padding-top: 1rem;
    text-align: center;
    font-family: var(--font-sans);
    font-size: 15px;
    opacity: 0.6;
  }
</style>
