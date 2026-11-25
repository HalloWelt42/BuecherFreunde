<script lang="ts">
  import type { Snippet } from "svelte";
  import Symbol from "./Symbol.svelte";
  let { titel, symbol = "", breit = false, id = undefined, neben = undefined, children }: { titel: string; symbol?: string; breit?: boolean; id?: string; neben?: Snippet; children: Snippet } = $props();
</script>

<section class="karte platte" class:breit {id}>
  <h2>{#if symbol}<Symbol name={symbol} />{/if}{titel}{#if neben}<span class="schiebt reihe neben">{@render neben()}</span>{/if}</h2>
  {@render children()}
</section>

<style>
  .neben {
    font-weight: 400;
  }
</style>
