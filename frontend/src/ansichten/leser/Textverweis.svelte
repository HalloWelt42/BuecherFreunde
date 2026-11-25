<script lang="ts">
  import { getContext, type Snippet } from "svelte";
  import { sichereAdresse } from "../../lib/leser/text/markdown";
  let { href = "", title = undefined, children = undefined }: { href?: string; title?: string; children?: Snippet } = $props();
  let adresse = $derived(sichereAdresse(href));

  const sprung = getContext<((kennung: string) => void) | undefined>("lesesprung");

  // Sprungmarken im Text: zur Überschrift, die Adresse bleibt
  function springe(e: MouseEvent) {
    e.preventDefault();
    sprung?.(decodeURIComponent(adresse.slice(1)));
  }
</script>

{#if adresse.startsWith("#")}
  <a href={adresse} {title} onclick={springe}>{@render children?.()}</a>
{:else if adresse}
  <a href={adresse} {title} target="_blank" rel="noopener noreferrer">{@render children?.()}</a>
{:else}
  <span {title}>{@render children?.()}</span>
{/if}
