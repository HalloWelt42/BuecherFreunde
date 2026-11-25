<script lang="ts">
  import type { Fundbuch } from "../../../lib/api/gutenberg";
  import { formatName, sprache, zahl } from "../../../lib/format";
  import Ersatzumschlag from "../../../lib/teile/Ersatzumschlag.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { buch, gewaehlt, onschalte }: { buch: Fundbuch; gewaehlt: boolean; onschalte: () => void } = $props();
  let kaputt = $state("");
  let angaben = $derived([buch.sprachen.map(sprache).join(", "), formatName(buch.download_format), buch.download_count ? `${zahl(buch.download_count)} mal geholt` : ""].filter(Boolean).join(", "));
</script>

<button type="button" class="treffer-karte platte" class:gewaehlt aria-pressed={gewaehlt} onclick={onschalte}>
  <span class="umschlag">
    {#if buch.cover_url && kaputt !== buch.cover_url}<img src={buch.cover_url} alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror={() => (kaputt = buch.cover_url)} />
    {:else}<Ersatzumschlag buch={{ id: buch.gutenberg_id, title: buch.titel, author: buch.autor }} />{/if}
  </span>
  <span class="text"><b>{buch.titel}</b><span class="klein">{buch.autor}</span><span class="leise zahl">{angaben}</span></span>
  <span class="marke" class:an={gewaehlt}><Symbol name="check" /></span>
</button>

<style>
  .treffer-karte {
    display: grid;
    grid-template-columns: 3.25rem minmax(0, 1fr) 1.625rem;
    gap: 0.75rem;
    padding: 0.5rem;
    align-items: start;
  }
  .treffer-karte:hover {
    background: var(--hauch);
  }
  .gewaehlt {
    background: var(--messing-hauch);
  }
  .text {
    display: grid;
    gap: 0.125rem;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  b {
    font: 600 1rem/1.25 var(--buchschrift);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .marke {
    width: 1.625rem;
    height: 1.625rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: 0.8125rem;
    color: transparent;
    background: var(--vertieft);
    box-shadow: inset 0 0 0 1px var(--linie);
  }
  .marke.an {
    background: var(--messing-flaeche);
    color: var(--auf-messing);
  }
</style>
