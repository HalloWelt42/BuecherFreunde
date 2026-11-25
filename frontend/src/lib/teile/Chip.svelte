<script lang="ts">
  import type { Snippet } from "svelte";
  import Symbol from "./Symbol.svelte";

  interface Eigenschaften {
    text?: string;
    symbol?: string;
    zahl?: string | number;
    farbe?: string;
    gedrueckt?: boolean;
    href?: string;
    titel?: string;
    gesperrt?: boolean;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }
  let { text = "", symbol = "", zahl = undefined, farbe = undefined, gedrueckt = undefined, href = undefined, titel = undefined, gesperrt = false, onclick = undefined, children = undefined }: Eigenschaften = $props();
</script>

{#snippet inhalt()}
  {#if farbe}<span class="farbe" style:background={farbe} style:margin="0"></span>{/if}
  {#if symbol}<Symbol name={symbol} />{/if}
  {text}
  {#if zahl !== undefined}<span class="zahl">{zahl}</span>{/if}
  {@render children?.()}
{/snippet}

{#if href}
  <a class="chip" {href} title={titel} aria-current={gedrueckt ? "page" : undefined} {onclick}>{@render inhalt()}</a>
{:else if onclick}
  <button class="chip" type="button" aria-pressed={gedrueckt} title={titel} disabled={gesperrt} {onclick}>{@render inhalt()}</button>
{:else}
  <span class="chip" title={titel}>{@render inhalt()}</span>
{/if}
