<script lang="ts">
  import { FARBTHEMEN, themaIndex } from "../../lib/leser/darstellung";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Eigenfarbe from "./Eigenfarbe.svelte";
  /** oneigen: eigene Farben sind möglich; dann ist die sechste Kachel dafür da */
  let { fg, bg, onwahl, oneigen = undefined }: { fg: string; bg: string; onwahl: (nr: number) => void; oneigen?: (neu: { fg?: string; bg?: string }) => void } = $props();
  let jetzt = $derived(themaIndex(fg, bg));
  let offen = $state(false);
</script>

<div class="tastenraster" role="group" aria-label="Farbthema">
  {#each FARBTHEMEN as t, n (t.name)}
    <button type="button" class="chip kachel" style:background={t.bg} style:color={t.fg} aria-pressed={n === jetzt} onclick={() => onwahl(n)}><Symbol name={t.symbol} />{t.name}</button>
  {/each}
  {#if oneigen}
    <button type="button" class="chip kachel" style:background={jetzt < 0 ? bg : undefined} style:color={jetzt < 0 ? fg : undefined} aria-pressed={jetzt < 0} aria-expanded={offen} onclick={() => (offen = !offen)}><Symbol name="palette" />Eigene</button>
  {/if}
</div>
{#if oneigen && offen}
  <Eigenfarbe name="Papier" wert={bg} onwahl={(neu) => oneigen({ bg: neu })} />
  <Eigenfarbe name="Text" wert={fg} onwahl={(neu) => oneigen({ fg: neu })} />
{/if}

<style>
  .chip[aria-pressed="true"] {
    box-shadow: 0 0 0 2px var(--messing);
  }
</style>
