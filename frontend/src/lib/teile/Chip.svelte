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
    /** Nur das Zeichen zeigen, der Text wird Beschriftung und Hinweis (BF-68) */
    nur?: boolean;
    /** Ein Verweis öffnet in einem neuen Tab, etwa aus einem Fenster mit ungespeicherten Eingaben */
    neu?: boolean;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }
  let { text = "", symbol = "", zahl = undefined, farbe = undefined, gedrueckt = undefined, href = undefined, titel = undefined, gesperrt = false, nur = false, neu = false, onclick = undefined, children = undefined }: Eigenschaften = $props();
  let nurZeichen = $derived(nur && !!symbol);
  let hinweis = $derived(titel ?? (nurZeichen ? text : undefined));
</script>

{#snippet inhalt()}
  {#if farbe}<span class="farbe" style:background={farbe} style:margin="0"></span>{/if}
  {#if symbol}<Symbol name={symbol} />{/if}
  {#if !nurZeichen}{text}{/if}
  {#if zahl !== undefined}<span class="zahl">{zahl}</span>{/if}
  {@render children?.()}
{/snippet}

{#if href}
  <a class="chip" class:nur={nurZeichen} {href} target={neu ? "_blank" : undefined} rel={neu ? "noopener" : undefined} title={hinweis} aria-label={nurZeichen ? text : undefined} aria-current={gedrueckt ? "page" : undefined} {onclick}>{@render inhalt()}</a>
{:else if onclick}
  <button class="chip" class:nur={nurZeichen} type="button" aria-pressed={gedrueckt} title={hinweis} aria-label={nurZeichen ? text : undefined} disabled={gesperrt} {onclick}>{@render inhalt()}</button>
{:else}
  <span class="chip" class:nur={nurZeichen} title={hinweis}>{@render inhalt()}</span>
{/if}
