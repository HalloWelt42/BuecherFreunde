<script lang="ts">
  // Umschlag eines Buchs: immer das Deckblatt vom Server; ein gezeichneter Ersatz nur für reine Textdateien und wenn es ausbleibt
  import { coverUrl } from "../api/books";
  import { formatName } from "../format";
  import { regalfarben } from "../schale/regalfarben";
  import Ersatzumschlag from "./Ersatzumschlag.svelte";

  interface Buchbild {
    id: number;
    title: string;
    author?: string;
    updated_at?: string;
    cover_path?: string;
    cover_stand?: number;
    file_format?: string;
  }
  let { buch, sofort = false, format = false }: { buch: Buchbild; sofort?: boolean; format?: boolean } = $props();

  let adresse = $derived(coverUrl(buch.id, buch.cover_stand || buch.updated_at));
  let fertig = $state("");
  let kaputt = $state("");
  let ohneBild = $derived((buch.cover_path === "" && ["txt", "md"].includes(buch.file_format ?? "")) || kaputt === adresse);

  function geladen(e: Event) {
    fertig = adresse;
    regalfarben.sammle(buch.id, e.currentTarget as HTMLImageElement);
  }
</script>

<span class="umschlag" class:leer={!ohneBild && fertig !== adresse}>
  {#if ohneBild}
    <Ersatzumschlag {buch} />
  {:else}
    <img src={adresse} alt="" loading={sofort ? "eager" : "lazy"} decoding="async" draggable="false" onload={geladen} onerror={() => (kaputt = adresse)} />
  {/if}
  {#if format && buch.file_format}<span class="format">{formatName(buch.file_format)}</span>{/if}
</span>
