<script lang="ts">
  import { untrack } from "svelte";
  import { speichereAnweisung, type Anweisung } from "../../lib/api/ai";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Regler from "../../lib/teile/Regler.svelte";

  let { anweisung, onschliessen, ongespeichert }: { anweisung: Anweisung; onschliessen: () => void; ongespeichert: () => void } = $props();

  let angaben = $state(untrack(() => ({ name: anweisung.name, beschreibung: anweisung.beschreibung ?? "", system_prompt: anweisung.system_prompt, temperatur: anweisung.temperatur, max_tokens: anweisung.max_tokens, aktiv: !!anweisung.aktiv })));
  let laeuft = $state(false);
  let fehler = $state("");

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    try {
      await speichereAnweisung(anweisung.id, $state.snapshot(angaben));
      melde.gut("Anweisung gespeichert");
      ongespeichert();
      onschliessen();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      laeuft = false;
    }
  }
</script>

<Fenster titel="Anweisung bearbeiten" breite="42rem" {onschliessen}>
  <form id="anweisungsformular" class="formular" onsubmit={speichere}>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={angaben.name} required /></label>
    <label class="feld">Beschreibung<input class="eingabe" bind:value={angaben.beschreibung} /></label>
    <Haekchen text="Aktiv" an={angaben.aktiv} onwahl={(an) => (angaben.aktiv = an)} />
    <label class="feld">Anweisung<textarea class="eingabe" rows="10" bind:value={angaben.system_prompt} required></textarea></label>
    <div class="zweifeld">
      <Regler name="Temperatur" wert={angaben.temperatur} von={0} bis={2} schritt={0.1} anzeige={angaben.temperatur.toFixed(1).replace(".", ",")} onwahl={(w) => (angaben.temperatur = w)} />
      <Regler name="Länge der Antwort, höchstens" wert={angaben.max_tokens} von={50} bis={4000} schritt={50} anzeige="{angaben.max_tokens} Token" onwahl={(w) => (angaben.max_tokens = w)} />
    </div>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="anweisungsformular" disabled={laeuft || !angaben.name.trim() || !angaben.system_prompt.trim()}>Speichern</button>
    </span>
  {/snippet}
</Fenster>
