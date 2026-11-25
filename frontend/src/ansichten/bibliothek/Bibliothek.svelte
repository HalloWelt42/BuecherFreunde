<script lang="ts">
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { buecher } from "../../lib/stand/buecher.svelte";
  import { filter } from "../../lib/stand/filter.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import { rollstand } from "../../lib/rollstand";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Nachlader from "../../lib/teile/Nachlader.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { untrack } from "svelte";
  import { regalansicht } from "./ansicht.svelte";
  import Detailliste from "./Detailliste.svelte";
  import Liste from "./Liste.svelte";
  import Regal from "./Regal.svelte";
  import Weiterlesen from "./Weiterlesen.svelte";
  import Werkzeugzeile from "./Werkzeugzeile.svelte";

  let art = $derived(regalansicht.art);
  let leer = $derived(buecher.geladen && !buecher.laedt && !buecher.fehler && !buecher.liste.length);

  // Andere Filter: Liste von vorn. Beim Zurückkommen steht dieselbe Liste schon da und wird nur aufgefrischt.
  let zuletzt = buecher.kennung;
  $effect(() => {
    const k = filter.kennung;
    untrack(() => {
      if (buecher.geladen && k === zuletzt) void buecher.auffrischen();
      else void buecher.laden();
      zuletzt = k;
    });
  });

  $effect(() => bestand.beiAenderung(() => void buecher.auffrischen()));
  $effect(() => wahl.falls(buecher.liste[0]));
  // Der Bearbeitungsmodus gehört zu dieser Ansicht
  $effect(() => () => auswahl.modus(false));
</script>

<Werkzeugzeile />

<div class="inhalt rollen" use:rollstand={`/?${filter.kennung}`}>
  {#if !filter.aktiv && !auswahl.bearbeiten}<Weiterlesen />{/if}

  {#if buecher.fehler}
    <Zustand art="fehler" text={buecher.fehler} onerneut={() => void buecher.laden()} />
  {:else if leer && filter.aktiv}
    <Zustand text="Kein Buch passt zu diesen Filtern."><Knopf text="Filter aufheben" symbol="xmark" klein onclick={() => filter.leere()} /></Zustand>
  {:else if leer}
    <Zustand text="Die Bibliothek ist noch leer."><Knopf text="Bücher hinzufügen" symbol="plus" klein haupt href="/import" /></Zustand>
  {:else if !buecher.liste.length}
    <Zustand art="laedt" text="Bücher werden geladen" />
  {/if}

  {#if buecher.liste.length}
    {#if art === "list"}<Liste liste={buecher.liste} />{:else if art === "detail-list"}<Detailliste liste={buecher.liste} />{:else}<Regal liste={buecher.liste} {art} />{/if}
    <Nachlader geladen={buecher.liste.length} gesamt={buecher.gesamt} laedt={buecher.laedt} onmehr={() => void buecher.mehr()} />
  {/if}
</div>
