<script lang="ts">
  // Unten im Darstellungsfeld: was für jedes Format gilt und am Telefon nicht in die Leiste passt
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import { randmarken } from "../../lib/leser/randschalter.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Vorlesen from "./Vorlesen.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();
</script>

{#if sitzung.mitStellen}<div class="feld">Rand<Haekchen text="Marken für Notizen und Markierungen" an={randmarken.an} onwahl={(an) => (randmarken.an = an)} /></div>{/if}
<div class="feld werkzeuge">
  Werkzeuge
  <div class="tastenraster">
    <Knopf klasse="kachel" text="Vollbild" symbol="expand" onclick={() => void schale.vollbildUmschalten()} />
    <Knopf klasse="kachel" text="Herunterladen" symbol="download" href={sitzung.fassung.anhang} download={sitzung.fassung.dateiname} />
    <Knopf klasse="kachel" text="Im Browser" titel="Im Browser öffnen" symbol="up-right-from-square" extern href={sitzung.fassung.datei} />
  </div>
</div>
{#if schale.telefon}<div class="feld werkzeuge">Vorlesen<Vorlesen {sitzung} /></div>{/if}

<style>
  .werkzeuge {
    border-top: 1px solid var(--linie);
    padding-top: 0.75rem;
  }
</style>
