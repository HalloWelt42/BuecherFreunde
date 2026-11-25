<script lang="ts">
  // Schrift wählen: zu sehen ist die gewählte, aufgeklappt alle in Gruppen, jede in sich selbst als Probe. Die Dateien kommen erst
  // beim Aufklappen.
  import { GRUPPEN, LESESCHRIFTEN, nutzeAlle, schriftZu } from "../../lib/leser/schriften";
  import Symbol from "../../lib/teile/Symbol.svelte";
  let { wert, mitBuch = false, onwahl }: { wert: string; mitBuch?: boolean; onwahl: (familie: string) => void } = $props();

  let offen = $state(false);
  let jetzt = $derived(wert ? schriftZu(wert) : undefined);

  function schalte() {
    offen = !offen;
    if (offen) nutzeAlle();
  }
</script>

<button type="button" class="chip gewaehlt" aria-expanded={offen} style:font-family={jetzt?.familie} onclick={schalte}>
  <span>{jetzt?.name ?? (mitBuch ? "Wie im Buch" : "Literata")}</span><Symbol name={offen ? "chevron-up" : "chevron-down"} />
</button>
{#if offen}
  <div class="schriften" role="group" aria-label="Schrift">
    {#if mitBuch}<div class="tastenraster" style:--spalten="2"><button type="button" class="chip" aria-pressed={!wert} onclick={() => onwahl("")}>Wie im Buch</button></div>{/if}
    {#each GRUPPEN as g (g)}
      <span class="gruppe">{g}</span>
      <div class="tastenraster" style:--spalten="2">
        {#each LESESCHRIFTEN.filter((s) => s.gruppe === g) as s (s.kennung)}
          <button type="button" class="chip" style:font-family={s.familie} aria-pressed={jetzt?.kennung === s.kennung} onclick={() => onwahl(s.familie)}>{s.name}</button>
        {/each}
      </div>
    {/each}
  </div>
{/if}

<style>
  .gewaehlt {
    width: 100%;
    justify-content: space-between;
    min-height: 2.25rem;
    font-size: 1rem;
  }
  .schriften {
    display: grid;
    gap: 0.375rem;
    width: 100%;
  }
  .gruppe {
    font-size: 0.75rem;
    color: var(--tinte-3);
    margin-top: 0.25rem;
  }
</style>
