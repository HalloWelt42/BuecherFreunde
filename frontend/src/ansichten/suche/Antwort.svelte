<script lang="ts">
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { frage }: { frage: string } = $props();
</script>

{#if verbindungen.assistent}
  <Karte titel="Daraus eine Antwort machen" symbol="comments">
    <p>Der Assistent liest diese Stellen und antwortet mit Belegen. Jeder Beleg springt hierher zurück, an dieselbe Seite.</p>
    <div class="reihe"><Knopf text="Im Assistenten fragen" symbol="comments" klein extern href={verbindungen.frageAdresse(frage)} /></div>
  </Karte>
{/if}
