<script lang="ts">
  // Text mit Marken (lib/uebersetzung/marken.ts): die beanstandete Stelle markiert, Platzhalter als kleines Zeichen
  import { stuecke } from "../../lib/uebersetzung/marken";
  import Symbol from "../../lib/teile/Symbol.svelte";
  let { text, stelle = "" }: { text: string; stelle?: string } = $props();
  let teile = $derived(stuecke(text, stelle));
</script>

<span class="markentext">{#each teile as t, n (n)}{#if t.art === "platz"}<span class="platz" class:markiert={t.markiert} title="Bleibt, wie es ist: Code, Formel, Bild oder Zeichen"><Symbol name="code" /></span>{:else if t.markiert}<mark>{t.text}</mark>{:else}{t.text}{/if}{/each}</span>
