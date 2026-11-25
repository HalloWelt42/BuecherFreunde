<script lang="ts">
  // Unten im Darstellungsfeld: was für jedes Format gilt und am Telefon nicht in die Leiste passt
  import { dateiUrl } from "../../lib/api/books";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Vorlesen from "./Vorlesen.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();
</script>

<div class="feld werkzeuge">
  Werkzeuge
  <div class="tastenraster">
    <Knopf klasse="kachel" text="Vollbild" symbol="expand" onclick={() => void schale.vollbildUmschalten()} />
    <Knopf klasse="kachel" text="Herunterladen" symbol="download" href={dateiUrl(sitzung.buch.id)} download={sitzung.buch.file_name || sitzung.buch.title} />
    <Knopf klasse="kachel" text="Im Browser" titel="Im Browser öffnen" symbol="up-right-from-square" extern href={dateiUrl(sitzung.buch.id)} />
  </div>
</div>
{#if schale.telefon}<div class="feld werkzeuge">Vorlesen<Vorlesen {sitzung} /></div>{/if}

<style>
  .werkzeuge {
    border-top: 1px solid var(--linie);
    padding-top: 0.75rem;
  }
</style>
