<script lang="ts">
  // Rundes Foto, sonst die Anfangsbuchstaben in einer Buchfarbe
  import { autorenFotoUrl } from "../../lib/api/authors";
  import { VORGABE } from "../../lib/palette";
  import { anfangsbuchstaben, schriftAuf } from "./angaben";

  let { autor, gross = false, onbild = undefined }: { autor: { id: number; name: string; photo_path: string }; gross?: boolean; onbild?: (bild: HTMLImageElement) => void } = $props();

  let kaputt = $state(0);
  let farbe = $derived(VORGABE[autor.id % VORGABE.length][autor.id % 2]);
  let mitFoto = $derived(!!autor.photo_path && kaputt !== autor.id);
</script>

{#if mitFoto}
  <img class="bild" class:gross src={autorenFotoUrl(autor.id, gross ? "normal" : "thumb")} alt="" loading={gross ? "eager" : "lazy"} onload={(e) => onbild?.(e.currentTarget as HTMLImageElement)} onerror={() => (kaputt = autor.id)} />
{:else}
  <span class="bild" class:gross style:background={farbe} style:color={schriftAuf(farbe)} aria-hidden="true">{anfangsbuchstaben(autor.name)}</span>
{/if}

<style>
  .bild {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    object-fit: cover;
    font: 600 1rem var(--buchschrift);
    box-shadow: 0 0 0 1px var(--linie);
  }
  .bild.gross {
    width: 100%;
    height: auto;
    aspect-ratio: 4 / 5;
    border-radius: var(--r3);
    font-size: 3rem;
    object-position: 50% 20%;
    box-shadow: 0 0 0 1px var(--linie), 0 12px 24px -12px rgb(var(--schatten) / 0.6);
  }
</style>
