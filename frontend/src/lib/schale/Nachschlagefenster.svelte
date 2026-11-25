<script lang="ts">
  import { melde } from "../stand/meldungen.svelte";
  import { gespraech } from "../stand/gespraech.svelte";
  import { anschluesse } from "../stand/anschluesse.svelte";
  import { nachschlag } from "../stand/nachschlag.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { vorlesen } from "../stand/vorlesen.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Menue from "../teile/Menue.svelte";
  import Schwebefenster from "../teile/Schwebefenster.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Zustand from "../teile/Zustand.svelte";

  let a = $derived(nachschlag.artikel);
  let inhalt: HTMLElement | undefined = $state();
  let menueKnopf = $state<HTMLElement | null>(null);
  let menueOffen = $state(false);
  let bildWeg = $state("");

  // Neuer Artikel beginnt oben, ein Verweis an seiner Stelle
  $effect(() => {
    if (!a || !inhalt) return;
    const ziel = a.anker ? inhalt.querySelector(`#${CSS.escape(`ns-${a.anker}`)}`) : null;
    if (ziel) ziel.scrollIntoView({ block: "start" });
    else inhalt.scrollTop = 0;
  });

  // Verweise im Artikel öffnen hier im Fenster
  function folge(e: MouseEvent) {
    const verweis = (e.target as Element).closest<HTMLElement>("a[data-pfad]");
    if (!verweis || !a) return;
    e.preventDefault();
    void nachschlag.lies({ buch: a.buch, pfad: verweis.dataset.pfad!, anker: "" });
  }

  function suchen(e: SubmitEvent) {
    e.preventDefault();
    void nachschlag.suche(nachschlag.wort);
  }

  const text = () => inhalt?.querySelector(".artikel")?.textContent?.trim() ?? "";

  function tun(arbeit: () => void) {
    menueOffen = false;
    arbeit();
  }

  async function kopiere() {
    await navigator.clipboard.writeText(`${a?.titel}\n\n${text()}`);
    melde.gut("Kopiert");
  }

  function inDieNotiz() {
    if (!a) return;
    notizblock.haengeAn(`${a.titel}: ${text().slice(0, 600)}\n${a.adresse}`);
    melde.gut("In der Schnellnotiz");
  }
</script>

<Schwebefenster merkname="bf-nachschlag-ort" titel="Nachschlagen" symbol="book-atlas" klasse="nachschlagefenster" stufe={1} onschliessen={() => nachschlag.schliesse()}>
  {#snippet knoepfe()}
    {#if nachschlag.kannZurueck}<Knopf text="Zurück" symbol="arrow-left" nur klein frei onclick={() => void nachschlag.zurueck()} />{/if}
    {#if a}
      <Knopf text={anschluesse.lexikonOeffnen} symbol="arrow-up-right-from-square" nur klein frei extern href={a.adresse} />
      <Knopf text="Mehr" symbol="ellipsis" nur klein frei aufgeklappt={menueOffen} bind:element={menueKnopf} onclick={() => (menueOffen = !menueOffen)} />
    {/if}
  {/snippet}

  <form class="suchzeile" onsubmit={suchen}>
    <input class="eingabe" type="search" aria-label="Nachschlagen" placeholder="Wort oder Begriff" enterkeyhint="search" bind:value={nachschlag.wort} />
    <Knopf text="Suchen" symbol="magnifying-glass" nur klein art="submit" laeuft={nachschlag.laedt} gesperrt={!nachschlag.wort.trim()} />
  </form>

  <div class="inhalt rollen" bind:this={inhalt}>
    {#if nachschlag.fehler}
      <Zustand art="fehler" text={nachschlag.fehler} onerneut={() => void nachschlag.suche(nachschlag.wort)} />
    {:else if a}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="artikel" lang="de" onclick={folge}>
        <p class="leise herkunft">{a.buchtitel}</p>
        <h1>{a.titel}</h1>
        {#if a.bild && bildWeg !== a.bild}<img src={a.bild} alt="" loading="lazy" onerror={() => (bildWeg = a!.bild)} />{/if}
        <!-- Der Server lässt nur Text, Überschriften, Listen und Verweise ins selbe Lexikon durch -->
        {@html a.html}
      </div>
    {:else if nachschlag.laedt}
      <Zustand art="laedt" text="Wird nachgeschlagen" />
    {:else if nachschlag.treffer.length}
      <ul>
        {#each nachschlag.treffer as t (t.buch + t.pfad)}
          <li><button type="button" onclick={() => void nachschlag.lies(t)}><b>{t.titel}</b><span class="leise">{t.buchtitel}</span>{#if t.auszug}<span class="auszug">{t.auszug}</span>{/if}</button></li>
        {/each}
      </ul>
    {:else if nachschlag.wort.trim()}
      <p class="leise">Nichts gefunden.</p>
    {/if}
  </div>
</Schwebefenster>

{#if menueOffen && a}
  <Menue anker={menueKnopf} name="Mehr" breite="15rem" onschliessen={() => (menueOffen = false)}>
    <div class="mehr">
      <Knopf text={anschluesse.lexikonOeffnen} symbol="arrow-up-right-from-square" klein frei extern href={a.adresse} onclick={() => (menueOffen = false)} />
      <Knopf text="Vorlesen" symbol="volume-low" klein frei onclick={() => tun(() => { vorlesen.pruefe(); vorlesen.entsperre(); vorlesen.lies(text(), a!.titel); })} />
      <Knopf text="Kopieren" symbol="copy" klein frei onclick={() => tun(() => void kopiere())} />
      <Knopf text="In die Schnellnotiz" symbol="note-sticky" klein frei onclick={() => tun(inDieNotiz)} />
      {#if anschluesse.jetzt.assistent}<Knopf text="Im Assistenten fragen" symbol="comments" klein frei onclick={() => tun(() => gespraech.oeffne({ text: text().slice(0, 4000), titel: a!.titel }))} />{/if}
    </div>
  </Menue>
{/if}

<style>
  .suchzeile {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.375rem;
    padding: 0 0.75rem 0.5rem;
  }
  .inhalt {
    padding: 0 0.75rem 0.75rem;
  }
  ul {
    display: grid;
    gap: 0.125rem;
    list-style: none;
    padding: 0;
    margin: 0;
  }
  li button {
    display: grid;
    gap: 0.125rem;
    width: 100%;
    min-height: 2.75rem;
    padding: 0.375rem 0.25rem;
    text-align: start;
    border: 0;
    border-top: 1px solid var(--linie);
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  li button:hover {
    background: var(--messing-hauch);
  }
  .auszug {
    display: -webkit-box;
    overflow: hidden;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .artikel {
    font: 400 1rem/1.55 var(--buchschrift);
    overflow-wrap: break-word;
    hyphens: auto;
  }
  .artikel h1 {
    margin: 0 0 0.5rem;
    font-size: 1.375rem;
    line-height: 1.2;
  }
  .herkunft {
    margin: 0;
    font: 500 0.8125rem/1.4 var(--schrift);
  }
  .artikel img {
    float: right;
    max-width: 40%;
    max-height: 11rem;
    margin: 0.125rem 0 0.5rem 0.75rem;
    border-radius: var(--r1, 3px);
  }
  .artikel :global(p) {
    margin: 0 0 0.75em;
  }
  .artikel :global(:is(h2, h3, h4)) {
    margin: 1em 0 0.375em;
    font-size: 1.125rem;
    line-height: 1.25;
  }
  .artikel :global(:is(ul, ol)) {
    margin: 0 0 0.75em;
    padding-inline-start: 1.25em;
  }
  .artikel :global(ul) {
    list-style: disc;
  }
  .artikel :global(ol) {
    list-style: decimal;
  }
  .artikel :global(a) {
    color: var(--messing);
  }
  .artikel :global(pre) {
    overflow: auto;
    font-size: 0.875rem;
  }
  .mehr {
    display: grid;
    justify-items: stretch;
  }
  .mehr :global(.knopf) {
    justify-content: start;
  }
</style>
