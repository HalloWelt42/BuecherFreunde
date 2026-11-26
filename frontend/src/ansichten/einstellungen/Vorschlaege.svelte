<script lang="ts">
  // Sammlungen finden (BF-66): Suchlauf mit Stand, danach die Vorschläge zum Anlegen, Anpassen oder Verwerfen
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Sammlungsvorschlag } from "../../lib/typen";
  import Vorschlag from "./Vorschlag.svelte";
  import Vorschlagsanpassung from "./Vorschlagsanpassung.svelte";
  import { vorschlaege } from "./sammlungsvorschlaege.svelte";

  /** Wie gefunden wird, wie im Entwurf in drei Stufen */
  const STUFEN: [string, string][] = [
    ["1. Regeln", "Reihenname mit Nummer im Titel oder im Dateinamen, gleicher Autor, Reihe aus den Angaben der Quellen"],
    ["2. Lokale KI", "prüft, ob die Bücher wirklich eine Reihe sind, fasst Schreibweisen zusammen und nennt sie"],
    ["3. Du", "siehst jeden Vorschlag mit seinen Büchern und legst ihn an, passt ihn an oder verwirfst ihn"],
  ];

  let anpassen = $state<Sammlungsvorschlag | null>(null);
  let stand = $derived(vorschlaege.stand);

  $effect(() => void vorschlaege.laden());
</script>

<Karte titel="Vorschläge" symbol="wand-magic-sparkles" breit id="vorschlaege">
  {#snippet neben()}<Knopf text="Sammlungen suchen" symbol="magnifying-glass" klein laeuft={vorschlaege.laeuft} onclick={() => void vorschlaege.suche()} />{/snippet}
  <div class="vorschlagsstufen">{#each STUFEN as [stufe, text] (stufe)}<div class="platte"><b>{stufe}</b><span>{text}</span></div>{/each}</div>
  {#if stand?.laeuft}
    <p class="reihe leise" role="status"><Symbol name="circle-notch" dreht /><span>{stand.schritt || "Läuft"}{stand.gefunden ? `, ${stand.gefunden} gefunden` : ""}</span></p>
  {:else if stand?.grund}
    <p class="marke-text warn">{stand.grund}</p>
  {/if}
  {#if vorschlaege.fehler}
    <p class="marke-text schlecht" role="alert">{vorschlaege.fehler}</p>
  {:else if vorschlaege.liste.length}
    <div class="vorschlaege">
      {#each vorschlaege.liste as v (v.id)}<Vorschlag vorschlag={v} onanpassen={() => (anpassen = v)} />{/each}
    </div>
  {:else if vorschlaege.geladen && !stand?.laeuft}
    <p class="leise">Keine offenen Vorschläge.</p>
  {/if}
</Karte>

{#if anpassen}<Vorschlagsanpassung vorschlag={anpassen} onschliessen={() => (anpassen = null)} />{/if}
