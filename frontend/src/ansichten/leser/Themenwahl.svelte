<script lang="ts">
  import { FARBTHEMEN, themaIndex } from "../../lib/leser/darstellung";
  import Symbol from "../../lib/teile/Symbol.svelte";
  let { fg, bg, onwahl }: { fg: string; bg: string; onwahl: (nr: number) => void } = $props();
  let jetzt = $derived(themaIndex(fg, bg));
</script>

<div class="reihe" role="group" aria-label="Farbthema">
  {#each FARBTHEMEN as t, n (t.name)}
    <button type="button" class="chip thema" style:background={t.bg} style:color={t.fg} aria-pressed={n === jetzt} title={t.name} onclick={() => onwahl(n)}><Symbol name={t.symbol} />{t.name}</button>
  {/each}
  {#if jetzt < 0}<span class="chip" style:background={bg} style:color={fg}>Eigene Farben</span>{/if}
</div>

<style>
  .thema[aria-pressed="true"] {
    box-shadow: 0 0 0 2px var(--messing);
  }
</style>
