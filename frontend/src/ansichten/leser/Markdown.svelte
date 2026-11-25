<script lang="ts">
  import SvelteMarkdown from "@humanspeak/svelte-markdown";
  import { untrack } from "svelte";
  import { entschaerfe, hinweiskasten, mitDiagramm } from "../../lib/leser/text/markdown";
  import Hinweiskasten from "./Hinweiskasten.svelte";
  import Textbild from "./Textbild.svelte";
  import Textverweis from "./Textverweis.svelte";
  let { quelle, onsteht }: { quelle: string; onsteht: () => void } = $props();

  let sauber = $derived(entschaerfe(quelle));
  const grund = { alert: Hinweiskasten, link: Textverweis, image: Textbild };

  // Diagramme brauchen eine große Bibliothek: nur holen, wenn das Buch eines hat
  async function teile() {
    if (!mitDiagramm(untrack(() => quelle))) return { erweiterungen: [hinweiskasten()], zeichner: grund };
    const { markedMermaid, MermaidRenderer } = await import("@humanspeak/svelte-markdown/extensions");
    return { erweiterungen: [markedMermaid(), hinweiskasten()], zeichner: { ...grund, mermaid: MermaidRenderer } };
  }

  function gesetzt(_knoten: HTMLElement) {
    onsteht();
  }
</script>

{#await teile() then t}
  <SvelteMarkdown source={sauber} extensions={t.erweiterungen as never} renderers={t.zeichner as never} />
  <span hidden use:gesetzt></span>
{/await}
