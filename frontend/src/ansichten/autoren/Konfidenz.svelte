<script lang="ts">
  // Wie sicher der Lexikoneintrag zum Autor passt, mit Erklärung auf Antippen
  import Menue from "../../lib/teile/Menue.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { PUNKTE, sicherheit, STUFEN } from "./angaben";

  let { stufe, punkte = 0 }: { stufe: string; punkte?: number } = $props();
  let offen = $state(false);
  let knopf: HTMLElement | null = $state(null);
  let s = $derived(sicherheit(stufe));
</script>

<button type="button" class="chip marke-text {s.ton}" aria-expanded={offen} title="Wie kommt das zustande?" bind:this={knopf} onclick={() => (offen = !offen)}>
  <Symbol name="shield-halved" />{s.wort}{punkte ? `, ${punkte} Punkte` : ""}
</button>

{#if offen}
  <Menue anker={knopf} name="Sicherheit des Lexikoneintrags" breite="22rem" onschliessen={() => (offen = false)}>
    <h2>Wie sicher ist das?</h2>
    <dl class="angaben">{#each PUNKTE as [n, text] (text)}<dt class="zahl">+{n}</dt><dd>{text}</dd>{/each}</dl>
    <h3>Stufen</h3>
    <dl class="angaben">{#each STUFEN as [wort, text] (wort)}<dt>{wort}</dt><dd>{text}</dd>{/each}</dl>
  </Menue>
{/if}

<style>
  .chip.gut {
    color: var(--gut);
  }
  .chip.warn {
    color: var(--warn);
  }
  .chip.schlecht {
    color: var(--schlecht);
  }
  h3 {
    margin: 0.75rem 0 0.25rem;
    font-size: 0.9375rem;
    font-weight: 600;
  }
</style>
