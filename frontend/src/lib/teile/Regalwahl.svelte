<script lang="ts">
  // Ein Regal suchen und wählen
  import { bestand } from "../stand/bestand.svelte";
  import type { Regal } from "../typen";
  import Symbol from "./Symbol.svelte";

  let { ohne = [], onwahl }: { ohne?: number[]; onwahl: (regal: Regal) => void } = $props();
  let suche = $state("");
  let passend = $derived(bestand.regale.filter((r) => !ohne.includes(r.id) && r.name.toLowerCase().includes(suche.trim().toLowerCase())));

  function fokussiere(knoten: HTMLInputElement) {
    knoten.focus();
  }

  function abschicken(e: SubmitEvent) {
    e.preventDefault();
    if (passend.length) onwahl(passend[0]);
  }
</script>

<form class="feld" onsubmit={abschicken}><input class="eingabe" type="search" placeholder="Regal suchen" aria-label="Regal suchen" bind:value={suche} use:fokussiere /></form>
<div class="liste">
  {#each passend as r (r.id)}
    <button type="button" class="punkt" onclick={() => onwahl(r)}><Symbol name={r.icon || "folder"} farbe={r.color} /><span class="name">{r.name}</span></button>
  {:else}<p class="leise">Kein Regal heißt so.</p>{/each}
</div>

<style>
  .liste {
    display: grid;
    max-height: 18rem;
    overflow: auto;
    margin-top: 0.5rem;
  }
</style>
