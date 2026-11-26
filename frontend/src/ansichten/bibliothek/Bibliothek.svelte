<script lang="ts">
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { buecher } from "../../lib/stand/buecher.svelte";
  import { filter } from "../../lib/stand/filter.svelte";
  import { ich } from "../../lib/stand/ich.svelte";
  import { schnellfilter } from "../../lib/stand/schnellfilter.svelte";
  import { suche } from "../../lib/stand/suche.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import { rollstand } from "../../lib/rollstand";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Nachlader from "../../lib/teile/Nachlader.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { untrack } from "svelte";
  import { regalansicht } from "./ansicht.svelte";
  import { regalfilter } from "./schnellfilter";
  import Detailliste from "./Detailliste.svelte";
  import Liste from "./Liste.svelte";
  import Regal from "./Regal.svelte";
  import Weiterlesen from "./Weiterlesen.svelte";
  import Werkzeugzeile from "./Werkzeugzeile.svelte";

  let art = $derived(regalansicht.art);
  let leer = $derived(buecher.geladen && !buecher.laedt && !buecher.fehler && !buecher.eintraege.length);
  let wort = $derived(filter.wert("q"));

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
  $effect(() => schnellfilter.biete(regalfilter));
  $effect(() => wahl.falls(buecher.liste[0]));
  // Der Bearbeitungsmodus gehört zu dieser Ansicht
  $effect(() => () => auswahl.modus(false));
</script>

<Werkzeugzeile />

<div class="inhalt rollen" use:rollstand={`/?${filter.kennung}`}>
  {#if !filter.aktiv && !wort && !auswahl.bearbeiten}<Weiterlesen />{/if}

  {#if buecher.fehler}
    <Zustand art="fehler" text={buecher.fehler} onerneut={() => void buecher.laden()} />
  {:else if leer && wort}
    <Zustand text={`Kein Buch passt zu "${wort}".`}>
      <Knopf text="Filter leeren" symbol="xmark" klein onclick={() => schnellfilter.leere(regalfilter)} />
      <Knopf text="In allen Büchern suchen" symbol="magnifying-glass" klein onclick={() => suche.suche(wort)} />
    </Zustand>
  {:else if leer && filter.aktiv}
    <Zustand text="Kein Buch passt zu diesen Filtern."><Knopf text="Filter aufheben" symbol="xmark" klein onclick={() => filter.leere()} /></Zustand>
  {:else if leer}
    <Zustand text="Die Bibliothek ist noch leer.">{#if ich.darf("hinzufuegen")}<Knopf text="Bücher hinzufügen" symbol="plus" klein haupt href="/import" />{/if}</Zustand>
  {:else if !buecher.eintraege.length}
    <Zustand art="laedt" text="Bücher werden geladen" />
  {/if}

  {#if buecher.eintraege.length}
    {#if art === "list"}<Liste eintraege={buecher.eintraege} />{:else if art === "detail-list"}<Detailliste eintraege={buecher.eintraege} />{:else}<Regal eintraege={buecher.eintraege} {art} />{/if}
    <Nachlader geladen={buecher.eintraege.length} gesamt={buecher.gesamtEintraege} laedt={buecher.laedt} onmehr={() => void buecher.mehr()} />
  {/if}
</div>
