<script lang="ts">
  import { aktualisiereKategorie, erstelleKategorie } from "../../lib/api/categories";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Farbwahl from "../../lib/teile/Farbwahl.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbolwahl from "../../lib/teile/Symbolwahl.svelte";
  import type { Regal } from "../../lib/typen";
  import { untrack } from "svelte";

  let { regal, onschliessen }: { regal: Regal | null; onschliessen: () => void } = $props();

  // Das Formular arbeitet auf einer Abschrift; gespeichert wird erst mit dem Knopf
  let angaben = $state(untrack(() => ({ name: regal?.name ?? "", description: regal?.description ?? "", color: regal?.color || "#6b7280", icon: regal?.icon ?? "", spezial: !!regal?.spezial })));
  let laeuft = $state(false);
  let fehler = $state("");

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    try {
      const daten = { ...angaben, name: angaben.name.trim(), parent_id: null };
      if (regal) await aktualisiereKategorie(regal.id, daten);
      else await erstelleKategorie(daten);
      bestand.geaendert();
      melde.gut(regal ? "Regal geändert" : "Regal angelegt");
      onschliessen();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      laeuft = false;
    }
  }
</script>

<Fenster titel={regal ? "Regal bearbeiten" : "Neues Regal"} {onschliessen}>
  <form id="regalformular" class="formular" onsubmit={speichere}>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={angaben.name} required maxlength="120" /></label>
    <!-- Die Antwort des Servers gleich unter dem Namen (meist gilt sie ihm), nie unten außer Sicht -->
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    <label class="feld">Beschreibung<input class="eingabe" bind:value={angaben.description} /></label>
    <Haekchen text="In der Leiste zeigen" an={angaben.spezial} onwahl={(an) => (angaben.spezial = an)} />
    <div class="feld">Farbe<Farbwahl wert={angaben.color} onwahl={(f) => (angaben.color = f)} /></div>
    <div class="feld">Symbol<Symbolwahl wert={angaben.icon} farbe={angaben.color} onwahl={(s) => (angaben.icon = s)} /></div>
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="regalformular" disabled={laeuft || !angaben.name.trim()}>{regal ? "Speichern" : "Anlegen"}</button>
    </span>
  {/snippet}
</Fenster>
