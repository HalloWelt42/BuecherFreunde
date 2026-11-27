<script lang="ts">
  // Bilder im Markdown: eingebettet (data:) oder von dieser Seite. Bilder aus dem Netz lässt die Content-Security-Policy nicht
  // zu (BF-5); statt eines kaputten Bildes steht dort ein ruhiger Platzhalter mit dem Alternativtext und dem Weg ins Netz.
  // Geholt wird nichts, auch nicht über den Server.
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { inhaltsbild } from "../../lib/inhaltsbild";
  let { href = "", title = undefined, text = "" }: { href?: string; title?: string; text?: string } = $props();

  let adresse = $derived(href.trim());
  let eingebettet = $derived(/^data:image\/(?:png|jpeg|gif|webp);/i.test(adresse));
  let netz = $derived.by(() => {
    try {
      const u = new URL(adresse);
      return /^https?:$/.test(u.protocol) ? u : null;
    } catch {
      return null;
    }
  });
  let vonHier = $derived(netz?.origin === location.origin);
  let kaputt = $state(false);
</script>

{#if (eingebettet || vonHier) && !kaputt}<img src={adresse} alt={text} {title} loading="lazy" use:inhaltsbild={() => (kaputt = true)} />
{:else if netz}<span class="netzbild" {title}><Symbol name="image" /><span class="alt">{text || "Bild"}</span><a href={netz.href} target="_blank" rel="noopener noreferrer">Im Netz öffnen</a></span>
{:else}<span {title}>[Bild: {text || href}]</span>{/if}

<style>
  .netzbild {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25em 0.625em;
    max-width: 100%;
    padding: 0.375em 0.625em;
    border: 1px dashed color-mix(in srgb, currentColor 35%, transparent);
    border-radius: 3px;
    font-size: 0.875em;
    line-height: 1.4;
  }
  .netzbild :global(i) {
    opacity: 0.6;
  }
  .alt {
    min-width: 0;
    overflow-wrap: anywhere;
    opacity: 0.8;
  }
</style>
