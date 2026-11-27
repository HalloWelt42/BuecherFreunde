<script lang="ts">
  import { anzahl, zahl } from "../../../lib/format";
  import { auftraege } from "../../../lib/stand/auftraege.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";

  let e = $derived(auftraege.ergaenzung);
  let gefunden = $derived(([["Umschläge", e.cover_gefunden], ["ISBN", e.isbn_gefunden], ["Angaben", e.metadaten_aktualisiert], ["Volltexte", e.volltext_extrahiert], ["Fehler", e.fehler]] as [string, number][]).filter(([, n]) => n > 0));

  async function halte() {
    try {
      await auftraege.ergaenzenAbbrechen();
    } catch (grund) {
      melde.schlecht(grund);
    }
  }
</script>

<div class="stand" aria-live="polite">
  <Balken anteil={e.gesamt ? e.fortschritt / e.gesamt : 0} gut={!e.laeuft} name="Bibliothek ergänzen" />
  <div class="reihe">
    <span class="leise zahl">{e.laeuft ? `Noch ${zahl(Math.max(0, e.gesamt - e.fortschritt))} von ${zahl(e.gesamt)}${e.aktuelles_buch ? `, ${e.aktuelles_buch}` : ""}` : `Fertig, ${zahl(e.fortschritt)} von ${zahl(e.gesamt)} geprüft`}</span>
    {#each gefunden as [text, n] (text)}<span class="marke-text zahl {text === 'Fehler' ? 'schlecht' : 'gut'}">{text} {zahl(n)}</span>{/each}
    {#if e.isbn_zur_wahl}<span class="marke-text zahl info">zur Wahl {zahl(e.isbn_zur_wahl)}</span>{/if}
    <span class="schiebt">
      {#if e.laeuft}<Knopf text="Anhalten" symbol="stop" klein onclick={() => void halte()} />{:else}<Knopf text="Ergebnis ausblenden" symbol="xmark" klein frei onclick={() => auftraege.ergebnisAusblenden()} />{/if}
    </span>
  </div>
  {#if e.grund}<p class="marke-text warn" role="status">Angaben angehalten: {e.grund}</p>{/if}
  {#if e.isbn_grund}<p class="marke-text warn" role="status">ISBN: {e.isbn_grund}{e.isbn_ungeprueft ? `; ${anzahl(e.isbn_ungeprueft, "Buch kam", "Bücher kamen")} ungeprüft zur Wahl` : ""}</p>{/if}
</div>

<style>
  .stand {
    display: grid;
    gap: 0.5rem;
  }
</style>
