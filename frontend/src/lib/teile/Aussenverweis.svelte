<script lang="ts">
  // Verweis in einer Antwort: öffnet immer im neuen Fenster, nur http und https
  import type { Snippet } from "svelte";
  let { href = "", title = "", children }: { href?: string; title?: string; children?: Snippet } = $props();
  let gilt = $derived(/^https?:\/\//i.test(href));
</script>

{#if gilt}<a {href} {title} target="_blank" rel="noopener noreferrer">{@render children?.()}</a>{:else}{@render children?.()}{/if}
