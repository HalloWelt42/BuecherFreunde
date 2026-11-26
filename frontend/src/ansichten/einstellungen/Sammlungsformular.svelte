<script lang="ts">
  import { aktualisiereSammlung, erstelleSammlung } from "../../lib/api/collections";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Farbwahl from "../../lib/teile/Farbwahl.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Sammlung } from "../../lib/typen";
  import { untrack } from "svelte";

  let { sammlung, onschliessen }: { sammlung: Sammlung | null; onschliessen: () => void } = $props();

  let angaben = $state(untrack(() => ({ name: sammlung?.name ?? "", description: sammlung?.description ?? "", color: sammlung?.color || "#1f9a82" })));
  let laeuft = $state(false);
  let fehler = $state("");

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    try {
      const daten = { ...angaben, name: angaben.name.trim() };
      if (sammlung) await aktualisiereSammlung(sammlung.id, daten);
      else await erstelleSammlung(daten);
      bestand.geaendert();
      melde.gut(sammlung ? "Sammlung geändert" : "Sammlung angelegt");
      onschliessen();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      laeuft = false;
    }
  }
</script>

<Fenster titel={sammlung ? "Sammlung bearbeiten" : "Neue Sammlung"} {onschliessen}>
  <form id="sammlungsformular" class="formular" onsubmit={speichere}>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={angaben.name} required maxlength="120" /></label>
    <!-- Die Antwort des Servers gleich unter dem Namen (meist gilt sie ihm), nie unten außer Sicht -->
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    <label class="feld">Beschreibung<textarea class="eingabe" rows="3" bind:value={angaben.description}></textarea></label>
    <div class="feld">Farbe<Farbwahl wert={angaben.color} onwahl={(f) => (angaben.color = f)} /></div>
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="sammlungsformular" disabled={laeuft || !angaben.name.trim()}>{sammlung ? "Speichern" : "Anlegen"}</button>
    </span>
  {/snippet}
</Fenster>
