<script lang="ts">
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { gespraech } from "../../lib/stand/gespraech.svelte";
  import { nachschlag } from "../../lib/stand/nachschlag.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { frage }: { frage: string } = $props();
</script>

{#if anschluesse.jetzt.assistent}
  <Karte titel="Daraus eine Antwort machen" symbol="comments">
    <p>Der Assistent liest diese Stellen und antwortet mit Belegen. Jeder Beleg springt hierher zurück, an dieselbe Seite.</p>
    <div class="reihe"><Knopf text="Im Assistenten fragen" symbol="comments" klein onclick={() => { gespraech.oeffne({}); void gespraech.frage(frage); }} />{#if anschluesse.jetzt.nachschlag}<Knopf text="Nachschlagen" symbol="book-atlas" klein onclick={() => nachschlag.oeffne(frage)} />{/if}</div>
  </Karte>
{/if}
