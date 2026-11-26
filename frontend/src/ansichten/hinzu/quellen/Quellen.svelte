<script lang="ts">
  // Andere Quellen: Eingangsordner, alte Sammlung, gemeinfreie Bücher
  import { gutenberg } from "../../../lib/stand/gutenberg.svelte";
  import { ladeEingangsordner, type Eingangsordner as Ordnerstand } from "../../../lib/api/annahme";
  import { annahme } from "../../../lib/stand/annahme.svelte";
  import { quellen as verzeichnisse } from "../../../lib/stand/quellen.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Eingangsordner from "./Eingangsordner.svelte";
  import Einleseliste from "./Einleseliste.svelte";
  import Gemeinfreie from "./Gemeinfreie.svelte";
  import Ordner from "./Ordner.svelte";

  type Quelle = "import" | "extern" | "gutenberg";

  /** Eingangsordner, in der Kellerwolke oder auf dem Gerät (ort) */
  let wolke = $state<Ordnerstand | null>(null);

  // Gemeinfreie Bücher nur, wenn die Quelle in der Einrichtung eingeschaltet ist
  let ohneGemeinfreie = $derived(verzeichnisse.aus("gutenberg"));
  const quellen: [Quelle, string, string, string][] = $derived([
    ["import", "folder-open", "Eingangsordner", !wolke?.bereit ? "einlesen, was im Ordner der App liegt" : wolke.ort === "kellerwolke" ? "in der Kellerwolke, wird beim Ablegen erkannt" : "auf dem Gerät, wird beim Ablegen erkannt"],
    ["extern", "hard-drive", "Alte Sammlung einlesen", "nur lesend, Doppel werden erkannt"],
    ...(ohneGemeinfreie ? [] : [["gutenberg", "landmark", "Gemeinfreie Bücher", "suchen nach Titel, Autor, Sprache"] as [Quelle, string, string, string]]),
  ]);

  let offen = $state<Quelle | "">(gutenberg.gesucht || gutenberg.laeuft ? "gutenberg" : "");

  $effect(() => void verzeichnisse.bereit());
  $effect(() => {
    if (ohneGemeinfreie && offen === "gutenberg") offen = "";
  });
  $effect(() => {
    ladeEingangsordner().then((o) => (wolke = o)).catch(() => {});
  });
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

{#if offen === "gutenberg"}<Gemeinfreie />{:else if offen === "import" && wolke?.bereit}<Eingangsordner ordner={wolke} onstand={(o) => (wolke = o)} />{:else if offen}{#key offen}<Ordner quelle={offen} />{/key}{/if}
{#if annahme.einlesen.gesamt}<Einleseliste />{/if}

<style>
  .offen {
    background: var(--messing-hauch);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--messing) 50%, transparent);
  }
</style>
