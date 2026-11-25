<script lang="ts">
  import { aktualisiereHighlight, loescheHighlight } from "../../lib/api/highlights";
  import { markierungsort, markierungstext } from "../../lib/leser/typen";
  import { Verzoegert } from "../../lib/leser/verzoegert";
  import { stellenAdresse } from "../../lib/lesestand";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln, Markierung } from "../../lib/typen";

  let { buch, m, ongeloescht }: { buch: BuchEinzeln; m: Markierung; ongeloescht: () => void } = $props();

  const KURZ = 180;
  const spaeter = new Verzoegert();
  let offen = $state(false);
  let name = $derived(m.label_name);
  let notiz = $derived(m.label_note);
  let text = $derived(markierungstext(m));

  // Was getippt, aber noch nicht gespeichert ist, geht beim Verlassen mit
  $effect(() => () => spaeter.alle());

  function speichere(feld: "label_name" | "label_note", wert: string) {
    if (feld === "label_name") name = wert;
    else notiz = wert;
    spaeter.rufe(feld, () => aktualisiereHighlight(m.id, { [feld]: wert }).catch((e) => melde.schlecht(e, "Nicht gespeichert")));
  }

  async function loesche() {
    const ja = await frage({ titel: "Markierung löschen?", text: `"${text.slice(0, KURZ)}"`, folgen: ["Die Stelle im Buch ist nicht mehr markiert.", ...(name || notiz ? ["Name und Notiz der Markierung gehen mit."] : [])], ja: "Löschen" });
    if (!ja) return;
    try {
      await loescheHighlight(m.id);
      ongeloescht();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    }
  }
</script>

<div class="stelle" style:--f={m.color}>
  <i></i>
  <div class="inhalt-stelle">
    <span class="zitat">{offen || text.length <= KURZ ? text : `${text.slice(0, KURZ)} ...`}</span>
    {#if offen}
      <input class="eingabe" placeholder="Name" aria-label="Name der Markierung" maxlength="50" value={name} oninput={(e) => speichere("label_name", e.currentTarget.value)} />
      <textarea class="eingabe" rows="2" placeholder="Notiz" aria-label="Notiz zur Markierung" value={notiz} oninput={(e) => speichere("label_note", e.currentTarget.value)}></textarea>
      <div class="reihe"><Knopf text="Löschen" symbol="trash" klein onclick={() => void loesche()} /></div>
    {:else if name || notiz}
      <span class="leise">{[name, notiz].filter(Boolean).join(": ")}</span>
    {/if}
  </div>
  <span class="griffe">
    <Chip text={markierungsort(m) || "Zur Stelle"} href={stellenAdresse(buch.id, buch.file_format, { cfi: m.cfi_range })} />
    <Knopf text="Ganzer Text, Name, Notiz" symbol={offen ? "chevron-up" : "pen"} nur klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} />
  </span>
</div>

<style>
  .inhalt-stelle {
    display: grid;
    gap: 0.375rem;
    min-width: 0;
    align-content: start;
    grid-template-columns: minmax(0, 1fr);
    overflow-wrap: anywhere;
  }
  .griffe {
    display: flex;
    align-items: start;
    gap: 0.125rem;
  }
</style>
