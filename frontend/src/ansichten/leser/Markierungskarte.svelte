<script lang="ts">
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { markierungsort, markierungstext } from "../../lib/leser/typen";
  import { schale } from "../../lib/stand/schale.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Markierung } from "../../lib/typen";
  import Farbreihe from "./Farbreihe.svelte";
  let { sitzung, m }: { sitzung: Lesesitzung; m: Markierung } = $props();
  let offen = $state(false);
  let ort = $derived(markierungsort(m));
  // Über ein Rechteck einer gescannten Seite (BF-123): solange gelesen wird, wartet, was den Text braucht
  let liest = $derived(m.lesen?.stand === "offen");
  let gescheitert = $derived(m.lesen?.stand === "fehler");
  function lies() {
    vorlesen.entsperre();
    vorlesen.lies(markierungstext(m), "Markierung");
  }

  function springe() {
    sitzung.griffe?.zurMarkierung(m);
    if (schale.telefon) sitzung.feld = "";
  }
</script>

<div class="stellenkarte" style:--f={m.color}>
  {#if liest}<span class="zitat leise lesend"><Symbol name="circle-notch" dreht />Text wird gelesen</span>
  {:else if gescheitert}<span class="zitat leise">Nicht gelesen: {m.lesen?.grund}</span>
    <div class="reihe"><Knopf text="Erneut lesen" symbol="rotate-right" klein frei onclick={() => void sitzung.leseErneut(m)} /></div>
  {:else if m.lesen && !m.text_snippet}<span class="zitat leise">{m.lesen.grund}</span>
  {:else}<span class="zitat">{markierungstext(m)}</span>{/if}
  {#if !offen && m.label_name}<span class="leise">{m.label_name}</span>{/if}
  <div class="reihe">
    <Knopf text={ort || "Zur Stelle"} symbol="arrow-right" klein frei onclick={springe} />
    <Knopf text="Farbe, Name, Notiz" symbol="pen" nur klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} />
    <Knopf text="Text kopieren" symbol="copy" nur klein frei gesperrt={liest || !m.text_snippet} onclick={() => void navigator.clipboard.writeText(markierungstext(m))} />
    <Knopf text="Vorlesen" symbol="volume-low" nur klein frei gesperrt={liest || !m.text_snippet} onclick={lies} />
    <Knopf text="An die Schnellnotiz" symbol="note-sticky" nur klein frei gesperrt={liest || !m.text_snippet} onclick={() => sitzung.anSchnellnotiz(`${ort ? `[${ort}] ` : ""}"${markierungstext(m)}"`)} />
    <Knopf text="Markierung löschen" symbol="trash" nur klein frei onclick={() => void sitzung.loescheMarkierung(m)} />
  </div>
  {#if offen}
    <Farbreihe name="Farbe der Markierung" wert={m.color} onwahl={(f) => sitzung.aendereMarkierung(m.id, { color: f })} />
    <input class="eingabe" placeholder="Name" aria-label="Name der Markierung" maxlength="50" value={m.label_name} oninput={(e) => sitzung.aendereMarkierung(m.id, { label_name: e.currentTarget.value })} />
    <textarea class="eingabe" rows="2" placeholder="Notiz" aria-label="Notiz zur Markierung" value={m.label_note} oninput={(e) => sitzung.aendereMarkierung(m.id, { label_note: e.currentTarget.value })}></textarea>
  {/if}
</div>

<style>
  .lesend {
    display: inline-flex;
    gap: 0.4em;
    align-items: center;
  }
</style>
