<script lang="ts">
  import { aktualisiereNotiz, loescheNotiz } from "../../lib/api/notes";
  import { Verzoegert } from "../../lib/leser/verzoegert";
  import { stellenAdresse } from "../../lib/lesestand";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln, Notiz } from "../../lib/typen";

  let { buch, n, ongeloescht }: { buch: BuchEinzeln; n: Notiz; ongeloescht: () => void } = $props();

  const spaeter = new Verzoegert();
  let offen = $state(false);
  let text = $derived(n.content);
  let ort = $derived(String(n.page_reference ?? "").trim());
  let mitStelle = $derived(!!ort || !!n.cfi_reference);

  $effect(() => () => spaeter.alle());

  function speichere(wert: string) {
    text = wert;
    spaeter.rufe("text", () => aktualisiereNotiz(n.id, { content: wert }).catch((e) => melde.schlecht(e, "Nicht gespeichert")));
  }

  async function loesche() {
    if (!(await frage({ titel: "Notiz löschen?", text: text.slice(0, 180), folgen: ["Die Notiz zu diesem Buch geht verloren."], ja: "Löschen" }))) return;
    try {
      await loescheNotiz(n.id);
      ongeloescht();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    }
  }
</script>

<div class="stelle">
  <i></i>
  <div class="inhalt-stelle">
    {#if offen}
      <textarea class="eingabe" rows="4" aria-label="Notiz" value={text} oninput={(e) => speichere(e.currentTarget.value)}></textarea>
      <div class="reihe"><Knopf text="Löschen" symbol="trash" klein onclick={() => void loesche()} /></div>
    {:else}
      <span class="zitat text">{text}</span>
    {/if}
    <span class="leise">Notiz</span>
  </div>
  <span class="griffe">
    {#if mitStelle}<Chip text={/^\d+$/.test(ort) ? `Seite ${ort}` : ort || "Zur Stelle"} href={stellenAdresse(buch.id, buch.file_format, { seite: ort, cfi: n.cfi_reference })} />{/if}
    <Knopf text="Notiz ändern" symbol={offen ? "chevron-up" : "pen"} nur klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} />
  </span>
</div>

<style>
  .inhalt-stelle {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
    align-content: start;
    grid-template-columns: minmax(0, 1fr);
    overflow-wrap: anywhere;
  }
  .text {
    white-space: pre-line;
  }
  .griffe {
    display: flex;
    align-items: start;
    gap: 0.125rem;
  }
</style>
