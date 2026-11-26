<script lang="ts">
  import { route } from "../../lib/router.svelte";
  import { aehnlicheBuecher, holeBuch, ladeUrl } from "../../lib/api/books";
  import { rollstand } from "../../lib/rollstand";
  import { filter } from "../../lib/stand/filter.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Buch, BuchEinzeln } from "../../lib/typen";
  import Ablageorte from "./Ablageorte.svelte";
  import Angabenvergleich from "./Angabenvergleich.svelte";
  import BuchBearbeiten from "./BuchBearbeiten.svelte";
  import Buchkopf from "./Buchkopf.svelte";
  import Buchsuche from "./Buchsuche.svelte";
  import Stellen from "./Stellen.svelte";
  import Verwandte from "./Verwandte.svelte";

  let { params }: { params: Record<string, string> } = $props();

  let id = $derived(Number(params.id));
  let buch = $state<BuchEinzeln | null>(null);
  let verwandt = $state<{ vom_autor: Buch[]; in_kategorie: Buch[] } | null>(null);
  let fehler = $state("");
  // Aus dem Kontextmenü eines Buchs kommt man mit ?bearbeiten gleich zum Bearbeiten (BF-42)
  let bearbeitet = $state("bearbeiten" in route.params);

  async function laden() {
    fehler = "";
    try {
      const geholt = await holeBuch(id);
      buch = geholt;
      wahl.waehle(geholt);
      aehnlicheBuecher(id).then((v) => (verwandt = v)).catch(() => (verwandt = null));
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => {
    void id;
    void laden();
  });
</script>

<div class="werkzeug">
  <Knopf text="Bibliothek" symbol="arrow-left" klein href={filter.letzteAdresse} />
  <span class="reihe schiebt">
    <Knopf text="Bearbeiten" symbol="pen" klein gedrueckt={bearbeitet} gesperrt={!buch} onclick={() => (bearbeitet = !bearbeitet)} />
    {#if buch}<Knopf text="Herunterladen" symbol="download" klein href={ladeUrl(buch.id)} download={buch.file_name || buch.title} />{/if}
  </span>
</div>

<div class="inhalt rollen" use:rollstand={`/book/${id}`}>
  {#if fehler && !buch}
    <Zustand art="fehler" text={fehler} onerneut={() => void laden()} />
  {:else if !buch}
    <Zustand art="laedt" text="Buch wird geladen" />
  {:else}
    {#if bearbeitet}
      <BuchBearbeiten {buch} onabbruch={() => (bearbeitet = false)} onfertig={() => { bearbeitet = false; void laden(); }} />
    {:else}
      <Buchkopf {buch} onneu={(neu) => buch && (buch = { ...buch, ...neu })} ongeaendert={() => void laden()} />
    {/if}
    <div class="raster">
      <Ablageorte {buch} />
      <Buchsuche {buch} />
      <Stellen {buch} />
      <Angabenvergleich {buch} ongeaendert={() => void laden()} />
      {#if verwandt}<Verwandte {verwandt} />{/if}
    </div>
  {/if}
</div>
