<script lang="ts">
  import SvelteMarkdown from "@humanspeak/svelte-markdown";
  import Chip from "../../lib/teile/Chip.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Drittanbieter from "./Drittanbieter.svelte";

  type Abschnitt = "lizenz" | "agb" | "drittanbieter" | "datenschutz" | "haftung" | "info";

  const abschnitte: [Abschnitt, string, string][] = [
    ["lizenz", "Lizenz", "scale-balanced"], ["agb", "AGB", "file-contract"], ["drittanbieter", "Drittanbieter", "cubes"],
    ["datenschutz", "Datenschutz", "shield-halved"], ["haftung", "Haftungsausschluss", "triangle-exclamation"], ["info", "Info", "circle-info"],
  ];

  let jetzt = $state<Abschnitt>("lizenz");
  let texte = $state<Partial<Record<Abschnitt, string>>>({});
  let fehler = $state("");

  async function hole(abschnitt: Abschnitt) {
    if (abschnitt === "drittanbieter" || texte[abschnitt]) return;
    fehler = "";
    try {
      const antwort = await fetch(`/legal/de/${abschnitt}.md`);
      if (!antwort.ok) throw new Error(`Der Text kam nicht an (${antwort.status})`);
      texte[abschnitt] = await antwort.text();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void hole(jetzt));
</script>

<div class="reihe" role="group" aria-label="Abschnitte">
  {#each abschnitte as [schluessel, text, symbol] (schluessel)}<Chip {text} {symbol} gedrueckt={jetzt === schluessel} onclick={() => (jetzt = schluessel)} />{/each}
</div>
{#if jetzt === "drittanbieter"}
  <Drittanbieter />
{:else if texte[jetzt]}
  {#key jetzt}<div class="rechtstext"><SvelteMarkdown source={texte[jetzt] ?? ""} /></div>{/key}
{:else if fehler}
  <Zustand art="fehler" text={fehler} onerneut={() => void hole(jetzt)} />
{:else}
  <Zustand art="laedt" text="Text wird geladen" />
{/if}
