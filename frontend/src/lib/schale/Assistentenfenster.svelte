<script lang="ts">
  import { tick } from "svelte";
  import SvelteMarkdown from "@humanspeak/svelte-markdown";
  import { entschaerfe } from "../leser/text/markdown";
  import { gespraech } from "../stand/gespraech.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { vorlesen } from "../stand/vorlesen.svelte";
  import Aussenverweis from "../teile/Aussenverweis.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Menue from "../teile/Menue.svelte";
  import Schwebefenster from "../teile/Schwebefenster.svelte";
  import Symbol from "../teile/Symbol.svelte";

  const VORSCHLAEGE: [string, string][] = [["Erklären", "Erkläre mir diese Stelle."], ["Kurz", "Fasse diese Stelle in wenigen Sätzen zusammen."], ["Einfach", "Erkläre diese Stelle so, dass es auch ohne Vorwissen verständlich ist."], ["Übersetzen", "Übersetze diese Stelle ins Deutsche."], ["Belegen", "Was steht in meinen anderen Büchern dazu? Nenne die Stellen."]];

  let text = $state("");
  let verlauf: HTMLElement | undefined = $state();
  let menueKnopf = $state<HTMLElement | null>(null);
  let menueOffen = $state(false);
  let letzte = $derived(gespraech.runden.at(-1));
  let mitStelle = $derived(!!gespraech.bezug.text?.trim());

  // Der Verlauf läuft mit der Antwort mit, solange man unten ist
  let unten = true;
  $effect(() => {
    void letzte?.antwort;
    void gespraech.runden.length;
    if (unten) void tick().then(() => verlauf && (verlauf.scrollTop = verlauf.scrollHeight));
  });

  function stelleFrage(frage: string) {
    unten = true;
    text = "";
    void gespraech.frage(frage);
  }

  function absenden(e?: SubmitEvent) {
    e?.preventDefault();
    if (gespraech.laeuft) return;
    if (text.trim()) stelleFrage(text.trim());
  }

  function taste(e: KeyboardEvent) {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    e.preventDefault();
    absenden();
  }

  function tun(arbeit: () => void) {
    menueOffen = false;
    arbeit();
  }

  async function kopiere() {
    await navigator.clipboard.writeText(letzte?.antwort ?? "");
    melde.gut("Kopiert");
  }

  function inDieNotiz() {
    notizblock.haengeAn(letzte?.antwort ?? "");
    melde.gut("In der Schnellnotiz");
  }
</script>

<Schwebefenster merkname="bf-assistent-ort" titel="Assistent" symbol="comments" klasse="assistentenfenster" stufe={2} onschliessen={() => gespraech.schliesse()}>
  {#snippet knoepfe()}
    {#if gespraech.adresse}<Knopf text="Im Assistenten öffnen" symbol="arrow-up-right-from-square" nur klein frei extern href={gespraech.adresse} />{/if}
    {#if gespraech.runden.length}<Knopf text="Mehr" symbol="ellipsis" nur klein frei aufgeklappt={menueOffen} bind:element={menueKnopf} onclick={() => (menueOffen = !menueOffen)} />{/if}
  {/snippet}

  <div class="verlauf rollen" bind:this={verlauf} onscroll={() => verlauf && (unten = verlauf.scrollHeight - verlauf.scrollTop - verlauf.clientHeight < 40)}>
    {#each gespraech.runden as r, n (n)}
      <div class="frage">{#if r.stelle}<q>{r.stelle.length > 220 ? `${r.stelle.slice(0, 220)}...` : r.stelle}</q>{/if}<p>{r.frage}</p></div>
      <div class="antwort" lang="de">
        {#if r.antwort}<SvelteMarkdown source={entschaerfe(r.antwort)} renderers={{ link: Aussenverweis } as never} />{/if}
        {#if r.laeuft && !r.antwort}<p class="leise"><Symbol name="circle-notch" dreht /> {r.wartetAuf ? `Wartet auf ${r.wartetAuf}` : "Denkt nach"}</p>{/if}
        {#if r.fehler}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />{r.fehler}</p>{/if}
        {#if r.belege.length}
          <ol class="belege">
            {#each r.belege as b (b.nummer)}<li value={Number(b.nummer) || undefined}>{#if b.verweis}<a href={b.verweis} target="_blank" rel="noopener">{b.titel}</a>{:else}{b.titel}{/if}{#if b.seite}<span class="leise">, Seite {b.seite}</span>{/if}</li>{/each}
          </ol>
        {/if}
      </div>
    {/each}
  </div>

  <form class="eingabezeile" onsubmit={absenden}>
    {#if mitStelle}
      <div class="stelle"><q>{gespraech.bezug.text}</q><Knopf text="Ohne diese Stelle" symbol="xmark" nur klein frei onclick={() => gespraech.loeseStelle()} /></div>
      <div class="vorschlaege">{#each VORSCHLAEGE as [name, frage] (name)}<Knopf text={name} klein gesperrt={gespraech.laeuft} onclick={() => stelleFrage(frage)} />{/each}</div>
    {:else if gespraech.bezug.titel}
      <p class="leise bezug">{gespraech.bezug.titel}</p>
    {/if}
    <div class="feld-zeile">
      <textarea class="eingabe" rows="2" aria-label="Frage an den Assistenten" placeholder={mitStelle ? "Frage zu dieser Stelle" : "Frage"} bind:value={text} onkeydown={taste}></textarea>
      {#if gespraech.laeuft}
        <Knopf text="Anhalten" symbol="stop" nur onclick={() => void gespraech.halt()} />
      {:else}
        <Knopf text="Fragen" symbol="paper-plane" nur haupt art="submit" gesperrt={!text.trim()} />
      {/if}
    </div>
  </form>
</Schwebefenster>

{#if menueOffen}
  <Menue anker={menueKnopf} name="Mehr" breite="16rem" onschliessen={() => (menueOffen = false)}>
    <div class="mehr">
      {#if gespraech.adresse}<Knopf text="Im Assistenten öffnen" symbol="arrow-up-right-from-square" klein frei extern href={gespraech.adresse} onclick={() => (menueOffen = false)} />{/if}
      {#if letzte?.antwort}
        <Knopf text="Antwort vorlesen" symbol="volume-low" klein frei onclick={() => tun(() => { vorlesen.pruefe(); vorlesen.entsperre(); vorlesen.lies(letzte!.antwort, "Antwort"); })} />
        <Knopf text="Antwort kopieren" symbol="copy" klein frei onclick={() => tun(() => void kopiere())} />
        <Knopf text="In die Schnellnotiz" symbol="note-sticky" klein frei onclick={() => tun(inDieNotiz)} />
      {/if}
      <Knopf text="Neues Gespräch" symbol="plus" klein frei onclick={() => tun(() => gespraech.neu())} />
    </div>
  </Menue>
{/if}

<style>
  .verlauf {
    display: grid;
    align-content: start;
    gap: 0.625rem;
    padding: 0 0.75rem 0.5rem;
  }
  .frage {
    justify-self: end;
    max-width: 88%;
    padding: 0.375rem 0.625rem;
    border-radius: var(--r2, 5px);
    background: var(--messing-hauch);
  }
  .frage p {
    margin: 0;
  }
  q {
    display: -webkit-box;
    overflow: hidden;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    quotes: none;
    font: italic 400 0.9375rem/1.45 var(--buchschrift);
  }
  .antwort {
    font: 400 1rem/1.55 var(--buchschrift);
    overflow-wrap: break-word;
    min-width: 0;
  }
  .antwort :global(p) {
    margin: 0 0 0.625em;
  }
  .antwort :global(:is(ul, ol):not(.belege)) {
    margin: 0 0 0.625em;
    padding-inline-start: 1.25em;
  }
  .antwort :global(ul) {
    list-style: disc;
  }
  .antwort :global(ol) {
    list-style: decimal;
  }
  .antwort :global(pre) {
    overflow: auto;
    font-size: 0.875rem;
  }
  .antwort :global(table) {
    display: block;
    overflow: auto;
  }
  .antwort :global(a) {
    color: var(--messing);
  }
  .belege {
    margin: 0.25rem 0 0;
    padding-inline-start: 1.5em;
    font: 500 0.875rem/1.4 var(--schrift);
  }
  .eingabezeile {
    display: grid;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem 0.75rem;
    border-top: 1px solid var(--linie);
  }
  .stelle,
  .feld-zeile {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.375rem;
    align-items: start;
  }
  .stelle q {
    -webkit-line-clamp: 2;
    line-clamp: 2;
    padding-inline-start: 0.5rem;
    border-inline-start: 2px solid var(--messing);
  }
  .vorschlaege {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }
  .bezug {
    margin: 0;
  }
  textarea {
    resize: none;
    width: 100%;
    font: inherit;
  }
  .mehr {
    display: grid;
    justify-items: stretch;
  }
  .mehr :global(.knopf) {
    justify-content: start;
  }
</style>
