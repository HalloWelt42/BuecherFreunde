<script lang="ts">
  // Einstieg des Lesers: Buch laden, Leser des Formats holen (pdf.js und die übrigen erst hier)
  import type { Component } from "svelte";
  import { holeBuch } from "../../lib/api/books";
  import { formatName } from "../../lib/format";
  import { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { leseziel, type Leseziel } from "../../lib/leser/ziel";
  import { navigate, route } from "../../lib/router.svelte";
  import { geraet } from "../../lib/stand/geraet.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import { schweige } from "../../lib/stand/vorlesen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { BuchEinzeln } from "../../lib/typen";

  type Formatleser = Component<{ buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void }>;

  let { params }: { params: Record<string, string> } = $props();

  const epub = () => import("./EpubLeser.svelte");
  const text = () => import("./TextLeser.svelte");
  const leser: Record<string, () => Promise<{ default: Formatleser }>> = { pdf: () => import("./PdfLeser.svelte"), epub, mobi: epub, txt: text, md: text };

  let id = $derived(Number(params.id));
  let buch = $state<BuchEinzeln | null>(null);
  let fehler = $state("");
  let sitzung = $derived(buch ? new Lesesitzung(buch) : null);
  async function lade(nummer: number) {
    fehler = "";
    buch = null;
    try {
      buch = await holeBuch(nummer);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade(id));

  $effect(() => {
    void sitzung?.laden();
    return () => sitzung?.beende();
  });

  $effect(() => () => {
    schweige();
    if (schale.vollbild) void schale.vollbildUmschalten();
  });

  // Am Telefon zurück, woher man kam (Suche, Weiterlesen, Assistent), sonst zur Buchseite
  function zurueck() {
    if (geraet.telefon && history.length > 1) history.back();
    else navigate(`/book/${id}`);
  }
</script>

{#if fehler}
  <div class="inhalt rollen">
    <Zustand art="fehler" text={fehler} onerneut={() => void lade(id)}><Knopf text="Zur Buchseite" symbol="arrow-left" klein href="/book/{id}" /></Zustand>
  </div>
{:else if buch && sitzung}
  {@const hole = leser[buch.file_format]}
  {#if hole}
    {#key `${buch.id}?${route.qs}`}
      {#await hole()}
        <div class="lesehinweis"><Zustand art="laedt" text="Leser wird geladen" /></div>
      {:then { default: Format }}
        <Format {buch} {sitzung} ziel={leseziel(location.search)} onzurueck={zurueck} />
      {:catch grund}
        <div class="inhalt rollen"><Zustand art="fehler" text="Der Leser ließ sich nicht laden: {grund.message}" onerneut={() => location.reload()} /></div>
      {/await}
    {/key}
  {:else}
    <div class="inhalt rollen">
      <Zustand text="{formatName(buch.file_format)} lässt sich hier nicht lesen."><Knopf text="Zur Buchseite" symbol="arrow-left" klein href="/book/{id}" /></Zustand>
    </div>
  {/if}
{:else}
  <div class="lesehinweis"><Zustand art="laedt" text="Buch wird geladen" /></div>
{/if}
