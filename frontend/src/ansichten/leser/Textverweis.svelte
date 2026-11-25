<script lang="ts">
  import type { Snippet } from "svelte";
  import { sichereAdresse } from "../../lib/leser/text/markdown";
  let { href = "", title = undefined, children = undefined }: { href?: string; title?: string; children?: Snippet } = $props();
  let adresse = $derived(sichereAdresse(href));

  // Sprungmarken im Text: auf die Überschrift rollen, die Adresse bleibt
  function springe(e: MouseEvent) {
    e.preventDefault();
    document.getElementById(decodeURIComponent(adresse.slice(1)))?.scrollIntoView({ block: "start" });
  }
</script>

{#if adresse.startsWith("#")}
  <a href={adresse} {title} onclick={springe}>{@render children?.()}</a>
{:else if adresse}
  <a href={adresse} {title} target="_blank" rel="noopener noreferrer">{@render children?.()}</a>
{:else}
  <span {title}>{@render children?.()}</span>
{/if}
