<script lang="ts">
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { markierungsort, markierungstext } from "../../lib/leser/typen";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Markierung } from "../../lib/typen";
  import Farbreihe from "./Farbreihe.svelte";
  let { sitzung, m }: { sitzung: Lesesitzung; m: Markierung } = $props();
  let offen = $state(false);
  let ort = $derived(markierungsort(m));

  function springe() {
    sitzung.griffe?.zurMarkierung(m);
    if (schale.telefon) sitzung.feld = "";
  }
</script>

<div class="stellenkarte" style:--f={m.color}>
  <span class="zitat">{markierungstext(m)}</span>
  {#if !offen && m.label_name}<span class="leise">{m.label_name}</span>{/if}
  <div class="reihe">
    <Knopf text={ort || "Zur Stelle"} symbol="arrow-right" klein frei onclick={springe} />
    <Knopf text="Farbe, Name, Notiz" symbol="pen" nur klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} />
    <Knopf text="Text kopieren" symbol="copy" nur klein frei onclick={() => void navigator.clipboard.writeText(markierungstext(m))} />
    <Knopf text="An die Schnellnotiz" symbol="note-sticky" nur klein frei onclick={() => sitzung.anSchnellnotiz(`${ort ? `[${ort}] ` : ""}"${markierungstext(m)}"`)} />
    <Knopf text="Markierung löschen" symbol="trash" nur klein frei onclick={() => void sitzung.loescheMarkierung(m)} />
  </div>
  {#if offen}
    <Farbreihe name="Farbe der Markierung" wert={m.color} onwahl={(f) => sitzung.aendereMarkierung(m.id, { color: f })} />
    <input class="eingabe" placeholder="Name" aria-label="Name der Markierung" maxlength="50" value={m.label_name} oninput={(e) => sitzung.aendereMarkierung(m.id, { label_name: e.currentTarget.value })} />
    <textarea class="eingabe" rows="2" placeholder="Notiz" aria-label="Notiz zur Markierung" value={m.label_note} oninput={(e) => sitzung.aendereMarkierung(m.id, { label_note: e.currentTarget.value })}></textarea>
  {/if}
</div>
