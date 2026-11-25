<script lang="ts">
  import { auftraege } from "../stand/auftraege.svelte";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";

  let e = $derived(auftraege.ergaenzung);
  let gefunden = $derived(([["Umschläge", e.cover_gefunden], ["ISBN", e.isbn_gefunden], ["Angaben", e.metadaten_aktualisiert], ["Volltexte", e.volltext_extrahiert], ["Fehler", e.fehler]] as [string, number][]).filter(([, n]) => n > 0));
</script>

<div class="auftrag">
  <div class="reihe">
    <b>Bibliothek ergänzen</b>
    <span class="schiebt">
      {#if e.laeuft}<Knopf text="Anhalten" symbol="stop" klein frei onclick={() => void auftraege.ergaenzenAbbrechen()} />{:else}<Knopf text="Ausblenden" symbol="xmark" nur klein frei onclick={() => auftraege.ergebnisAusblenden()} />{/if}
    </span>
  </div>
  <Balken anteil={e.gesamt ? e.fortschritt / e.gesamt : 0} gut={!e.laeuft} name="Bibliothek ergänzen" />
  <span class="leise zahl">{e.laeuft ? `${e.fortschritt} von ${e.gesamt} Büchern${e.aktuelles_buch ? `, ${e.aktuelles_buch}` : ""}` : `Fertig, ${e.gesamt} Bücher geprüft`}</span>
  {#if gefunden.length}<span class="leise zahl">{gefunden.map(([t, n]) => `${t}: ${n}`).join(", ")}</span>{/if}
</div>

<style>
  .auftrag {
    display: grid;
    gap: 0.375rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--linie);
    overflow-wrap: anywhere;
  }
</style>
