<script lang="ts">
  import { zahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { vorgaenge } from "./vorgaenge.svelte";

  let z = $derived(bestand.zahlen);

  async function baue() {
    const ja = await frage({
      titel: "Suchindex neu aufbauen?",
      folgen: ["Bei vielen Büchern dauert das einige Minuten.", "Bis dahin findet die Suche nach Wörtern nur einen Teil.", "Bücher, Notizen und Lesestände ändern sich nicht."],
      ja: "Neu aufbauen",
      symbol: "arrows-rotate",
      gefahr: false,
    });
    if (ja) await vorgaenge.baueIndex();
  }
</script>

<dl class="angaben">
  <dt>Bücher im Bestand</dt><dd class="zahl">{zahl(z.buecher_gesamt)}</dd>
  <dt>mit ISBN</dt><dd class="zahl">{zahl(z.buecher_mit_isbn)}</dd>
  <dt>Dokumente</dt><dd class="zahl">{zahl(z.dokumente)}</dd>
  <dt>Autoren</dt><dd class="zahl">{zahl(z.autoren)}</dd>
  <dt>Regale</dt><dd class="zahl">{zahl(bestand.regale.length)}</dd>
  <dt>Sammlungen</dt><dd class="zahl">{zahl(bestand.sammlungen.length)}</dd>
</dl>
<p class="klein">Der Suchindex pflegt sich selbst. Neu aufbauen hilft nur, wenn die Suche Bücher übersieht.</p>
<div class="reihe"><Knopf text="Suchindex neu aufbauen" symbol="arrows-rotate" klein laeuft={vorgaenge.laeuft.index} onclick={() => void baue()} /></div>
