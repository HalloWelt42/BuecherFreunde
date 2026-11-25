<script lang="ts">
  // Andere Quellen: Eingangsordner, alte Sammlung, gemeinfreie Bücher
  import { gutenberg } from "../../../lib/stand/gutenberg.svelte";
  import { auftraege } from "../../../lib/stand/auftraege.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Einleseliste from "./Einleseliste.svelte";
  import Gemeinfreie from "./Gemeinfreie.svelte";
  import Ordner from "./Ordner.svelte";

  type Quelle = "import" | "extern" | "gutenberg";

  const quellen: [Quelle, string, string, string][] = [
    ["import", "folder-open", "Eingangsordner", "einlesen, was im Ordner der App liegt"],
    ["extern", "hard-drive", "Alte Sammlung einlesen", "nur lesend, Doppel werden erkannt"],
    ["gutenberg", "landmark", "Gemeinfreie Bücher", "suchen nach Titel, Autor, Sprache"],
  ];

  let offen = $state<Quelle | "">(gutenberg.gesucht || gutenberg.laeuft ? "gutenberg" : "");

  $effect(() => void gutenberg.pruefe());
</script>

<section class="block">
  <div class="titelzeile"><h2>Andere Quellen</h2></div>
  <div class="quellen">
    {#each quellen as [wert, symbol, text, unter] (wert)}
      <button type="button" class="platte" class:offen={offen === wert} aria-expanded={offen === wert} onclick={() => (offen = offen === wert ? "" : wert)}>
        <Symbol name={symbol} /><span><b>{text}</b><br /><span class="leise">{unter}</span></span>
      </button>
    {/each}
  </div>
</section>

{#if offen === "gutenberg"}<Gemeinfreie />{:else if offen}{#key offen}<Ordner quelle={offen} />{/key}{/if}
{#if auftraege.aufgaben.length}<Einleseliste />{/if}

<style>
  .offen {
    background: var(--messing-hauch);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--messing) 50%, transparent);
  }
</style>
