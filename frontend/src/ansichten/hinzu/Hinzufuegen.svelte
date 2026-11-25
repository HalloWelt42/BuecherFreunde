<script lang="ts">
  import type { Gruppe } from "../../lib/annahme/zeilen";
  import { annahme } from "../../lib/stand/annahme.svelte";
  import { rollstand } from "../../lib/rollstand";
  import Chip from "../../lib/teile/Chip.svelte";
  import Ablage from "./Ablage.svelte";
  import Aufnahmen from "./Aufnahmen.svelte";
  import Ergaenzen from "./quellen/Ergaenzen.svelte";
  import Quellen from "./quellen/Quellen.svelte";

  type Filter = "alle" | Gruppe;
  const filter: [Filter, string][] = [["alle", "Alle"], ["laeuft", "Läuft"], ["klaeren", "Zu klären"], ["da", "Schon da"], ["fertig", "Fertig"]];
  let gewaehlt = $state<Filter>("alle");
  let ablage: Ablage | undefined = $state();

  let zeilen = $derived(gewaehlt === "alle" ? annahme.zeilen : annahme.zeilen.filter((z) => z.gruppe === gewaehlt));
  const zahl = (f: Filter) => (f === "alle" ? annahme.zeilen : annahme.zeilen.filter((z) => z.gruppe === f)).length;
</script>

<div class="werkzeug">
  <h1>Hinzufügen</h1>
  <span class="leise">Jede Datei geht gleich in die Kellerwolke</span>
  <span class="reihe schiebt">{#each filter as [wert, text] (wert)}<Chip {text} zahl={zahl(wert)} gedrueckt={gewaehlt === wert} onclick={() => (gewaehlt = wert)} />{/each}</span>
</div>

<div class="inhalt rollen" use:rollstand={"/import"}>
  <Ablage bind:this={ablage} />
  <Aufnahmen {zeilen} onwaehlen={() => ablage?.waehle()} />
  <Quellen />
  <Ergaenzen />
</div>
