<script lang="ts">
  import type { Snippet } from "svelte";
  import Symbol from "./Symbol.svelte";

  interface Eigenschaften {
    text: string;
    symbol?: string;
    /** Nur das Zeichen zeigen, der Text wird Beschriftung und Hinweis */
    nur?: boolean;
    /** Ein kürzeres Wort für enge Reihen; welches gilt, bestimmt der Stil der Reihe (.lang und .kurz) */
    kurz?: string;
    klein?: boolean;
    haupt?: boolean;
    frei?: boolean;
    gedrueckt?: boolean;
    aufgeklappt?: boolean;
    gesperrt?: boolean;
    /** Der Vorgang dieses Knopfs läuft: das Zeichen dreht, und der Knopf ist so lange gesperrt */
    laeuft?: boolean;
    /** Es wird gerade etwas geholt: das Zeichen dreht, der Knopf bleibt bedienbar (Pause beim Vorlesen, BF-121) */
    dreht?: boolean;
    href?: string;
    download?: string | boolean;
    extern?: boolean;
    titel?: string;
    art?: "button" | "submit";
    klasse?: string;
    element?: HTMLElement | null;
    onclick?: (e: MouseEvent) => void;
    children?: Snippet;
  }

  let { text, symbol = "", nur = false, kurz = undefined, klein = false, haupt = false, frei = false, gedrueckt = undefined, aufgeklappt = undefined, gesperrt = false, laeuft = false, dreht = false,
    href = undefined, download = undefined, extern = false, titel = undefined, art = "button", klasse = "", element = $bindable(null), onclick = undefined, children = undefined }: Eigenschaften = $props();

  let klassen = $derived(["knopf", klasse, nur && "nur", klein && "klein", haupt && "haupt", frei && "frei"].filter(Boolean).join(" "));
  let hinweis = $derived(titel ?? (nur ? text : undefined));
</script>

{#snippet inhalt()}
  {#if laeuft || dreht}<Symbol name="circle-notch" dreht />{:else if symbol}<Symbol name={symbol} />{/if}
  {#if nur}{:else if kurz}<span class="lang">{text}</span><span class="kurz">{kurz}</span>{:else}<span>{text}</span>{/if}
  {@render children?.()}
{/snippet}

{#if href && !gesperrt}
  <a class={klassen} {href} {download} target={extern ? "_blank" : undefined} rel={extern ? "noopener" : undefined} title={hinweis} aria-label={nur ? text : undefined} {onclick} bind:this={element}>{@render inhalt()}</a>
{:else}
  <button class={klassen} type={art} disabled={gesperrt || laeuft} title={hinweis} aria-label={nur ? text : undefined} aria-pressed={gedrueckt} aria-expanded={aufgeklappt} {onclick} bind:this={element}>{@render inhalt()}</button>
{/if}
