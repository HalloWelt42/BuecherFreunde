<script lang="ts">
  import { zahl as alsZahl } from "../format";
  import Symbol from "../teile/Symbol.svelte";
  let { text, symbol, symbolfarbe = undefined, zahl = undefined, gedrueckt = undefined, href = undefined, hier = false, onclick = undefined }: { text: string; symbol: string; symbolfarbe?: string; zahl?: number; gedrueckt?: boolean; href?: string; hier?: boolean; onclick?: () => void } = $props();
  // Die eigene Farbe eines Regals zeigt sich, sobald es gewählt ist; sonst bleibt die Leiste ruhig
  let farbe = $derived(gedrueckt ? symbolfarbe : undefined);
</script>

{#snippet inhalt()}
  <Symbol name={symbol} {farbe} /><span class="name" title={text}>{text}</span>{#if zahl !== undefined}<span class="zahl">{alsZahl(zahl)}</span>{/if}
{/snippet}

{#if href}
  <a class="punkt" {href} aria-current={hier ? "page" : undefined} {onclick}>{@render inhalt()}</a>
{:else}
  <button type="button" class="punkt" aria-pressed={gedrueckt} {onclick}>{@render inhalt()}</button>
{/if}
