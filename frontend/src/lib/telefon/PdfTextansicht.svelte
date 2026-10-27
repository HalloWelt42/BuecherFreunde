<script>
  // Textansicht eines PDF: die Seiten als umfließender Text statt fester Zeilen, mit Überschriften, Kästen und den
  // Abbildungen an ihrer Stelle (antippen vergrößert). Lädt ab der aktuellen Seite in Ausschnitten nach (unten von
  // selbst, oben auf Knopfdruck) und meldet die oberste sichtbare Seite als Leseposition.
  import "@fontsource/literata/400.css";
  import "@fontsource/literata/400-italic.css";
  import "@fontsource/literata/700.css";
  import "@fontsource/atkinson-hyperlegible/400.css";
  import "@fontsource/atkinson-hyperlegible/400-italic.css";
  import "@fontsource/atkinson-hyperlegible/700.css";
  import { untrack } from "svelte";
  import { textSeiten, textBildUrl } from "../api/books.js";
  import { textansicht } from "./textansicht.svelte.js";
  import TextEinstellungen from "./TextEinstellungen.svelte";
  import Bildlupe from "./Bildlupe.svelte";

  let {
    bookId,
    startSeite = 1,
    einstellungenOffen = $bindable(false),
    onSeite = () => {},
    onOriginal = () => {},
  } = $props();

  const AUSSCHNITT = 6;

  let seiten = $state([]);
  let gesamt = $state(0);
  let laedt = $state(false);
  let fehler = $state("");
  let flaeche = $state(null);
  let ende = $state(null);
  let lupe = $state(null);   // { quelle, beschreibung }

  let erste = $derived(seiten[0]?.nr ?? 1);
  let letzte = $derived(seiten.at(-1)?.nr ?? 0);
  let ohneText = $derived(seiten.length > 0 && seiten.every((s) => s.bausteine.length === 0));

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
    }, { root: flaeche, rootMargin: "800px 0px" });
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

  // Bildunterschrift direkt nach einer Abbildung beschreibt sie in der Lupe
  function beschreibungZu(bausteine, index) {
    const naechster = bausteine[index + 1];
    return naechster?.art === "unterschrift" ? naechster.text : "";
  }
</script>

{#snippet abbildung(seite, b, beschreibung)}
  <button class="abbildung" onclick={() => (lupe = { quelle: textBildUrl(bookId, seite.nr, b.bild), beschreibung })}
    aria-label="Abbildung vergrößern">
    <img src={textBildUrl(bookId, seite.nr, b.bild)} alt={beschreibung} loading="lazy"
      style:aspect-ratio={b.verhaeltnis || "auto"} />
  </button>
{/snippet}

<div
  class="textansicht"
  lang="de"
  bind:this={flaeche}
  onscroll={rollen}
  style:background-color={textansicht.thema.bg}
  style:color={textansicht.thema.fg}
>
  <div
    class="spalte"
    style:font-family={textansicht.familie}
    style:font-size="calc(18px * {textansicht.groesse} / 100)"
    style:line-height={textansicht.zeilenabstand}
  >
    {#if erste > 1}
      <button class="frueher" disabled={laedt} onclick={() => lade(Math.max(1, erste - AUSSCHNITT), true)}>
        Frühere Seiten
      </button>
    {/if}

    {#if ohneText}
      <div class="hinweis">
        <p>Diese Seiten haben keine lesbare Textschicht (etwa eingescannt), daher gibt es hier keinen Fließtext.</p>
        <button onclick={onOriginal}>Zur Originalansicht</button>
      </div>
    {/if}

    {#each seiten as seite (seite.nr)}
      <section data-seite={seite.nr}>
        <div class="seitenmarke">Seite {seite.gedruckt || seite.nr}</div>
        {#each seite.bausteine as b, i (i)}
          {#if b.art === "ueberschrift"}
            <h2>{b.text}</h2>
          {:else if b.art === "unterschrift"}
            <p class="unterschrift">{b.text}</p>
          {:else if b.art === "bild"}
            {@render abbildung(seite, b, beschreibungZu(seite.bausteine, i))}
          {:else if b.art === "kasten"}
            <aside class="kasten">
              {#if b.titel}<div class="kastentitel">{b.titel}</div>{/if}
              {#each b.inhalt as t, j (j)}
                {#if t.art === "bild"}
                  {@render abbildung(seite, t, "")}
                {:else}
                  <p>{t.text}</p>
                {/if}
              {/each}
            </aside>
          {:else}
            <p>{b.text}</p>
          {/if}
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

{#if einstellungenOffen}
  <TextEinstellungen onSchliessen={() => (einstellungenOffen = false)} />
{/if}

{#if lupe}
  <Bildlupe quelle={lupe.quelle} beschreibung={lupe.beschreibung} onSchliessen={() => (lupe = null)} />
{/if}

<style>
  .textansicht {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overflow-x: clip;
    transition: background-color 0.2s, color 0.2s;
  }

  .spalte {
    max-width: 42em;
    margin: 0 auto;
    padding: 1rem 1.25rem 3rem;
  }

  p {
    margin: 0 0 0.9em;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
    overflow-wrap: break-word;
  }

  h2 {
    margin: 1.4em 0 0.6em;
    font-size: 1.25em;
    line-height: 1.3;
    font-weight: 700;
  }

  .unterschrift {
    margin-top: -0.3em;
    font-size: 0.85em;
    line-height: 1.45;
    text-align: left;
    opacity: 0.8;
  }

  .abbildung {
    display: block;
    width: 100%;
    margin: 0.75em 0 0.9em;
    padding: 0;
    border: none;
    background: none;
    cursor: zoom-in;
  }

  .abbildung img {
    display: block;
    max-width: 100%;
    height: auto;
    margin: 0 auto;
    border-radius: 6px;
    background: #fff;
  }

  .kasten {
    margin: 1em 0 1.1em;
    padding: 0.75em 0.9em 0.1em;
    border-left: 4px solid currentColor;
    border-radius: 6px;
    background: color-mix(in srgb, currentColor 7%, transparent);
  }

  .kastentitel {
    margin-bottom: 0.5em;
    font-weight: 700;
    font-size: 0.95em;
  }

  .seitenmarke {
    margin: 1.25rem 0 0.75rem;
    font-family: var(--font-sans);
    font-size: 13px;
    line-height: 1.3;
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
