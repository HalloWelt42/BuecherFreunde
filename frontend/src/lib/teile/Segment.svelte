<script lang="ts" generics="W extends string">
  // Eine von wenigen Möglichkeiten, alle sichtbar
  import Symbol from "./Symbol.svelte";

  let { name, werte, wert, nurSymbole = false, gesperrt = false, onwahl }: { name: string; werte: [W, string, string?][]; wert: W; nurSymbole?: boolean; gesperrt?: boolean; onwahl: (w: W) => void } = $props();
</script>

<div class="segment" role="group" aria-label={name}>
  {#each werte as [w, text, symbol] (w)}
    <button type="button" aria-pressed={w === wert} title={nurSymbole ? text : undefined} aria-label={nurSymbole ? text : undefined} disabled={gesperrt} onclick={() => onwahl(w)}>
      {#if symbol}<Symbol name={symbol} />{/if}{#if !nurSymbole}{symbol ? " " : ""}{text}{/if}
    </button>
  {/each}
</div>
