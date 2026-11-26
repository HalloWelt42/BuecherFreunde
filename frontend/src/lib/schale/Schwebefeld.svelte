<script lang="ts">
  // Feld unter dem Kopf: Aufträge, Darstellung, Konto
  import type { Snippet } from "svelte";
  import { offenesFeld } from "../flucht";
  import { schale } from "../stand/schale.svelte";

  let { titel, breite = "21rem", children }: { titel: string; breite?: string; children: Snippet } = $props();
  let feld: HTMLElement | undefined = $state();

  // Der Kopf gehört dazu: seine Knöpfe öffnen und schließen die Felder selbst
  $effect(() => offenesFeld(() => [feld, document.querySelector(".kopf")], () => (schale.offen = "")));
</script>

<div class="schwebe unterm-kopf glas dicht" style:--breite={breite} role="dialog" aria-label={titel} bind:this={feld}>
  <div class="rollen">
    <h2>{titel}</h2>
    {@render children()}
  </div>
</div>

<style>
  .unterm-kopf {
    top: calc(var(--kopf) + 10px);
    --rechts: var(--fuge);
  }
</style>
