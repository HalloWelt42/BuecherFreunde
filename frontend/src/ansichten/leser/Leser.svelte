<script lang="ts">
  // Einstieg des Lesers: Buch und Fassung laden (das Original, unter /read/de die Übersetzung, BF-71, unter /read/format/epub ein
  // weiteres Format, BF-80, unter /material/<kennung> Begleitmaterial, BF-81), Leser des Formats holen (pdf.js und die übrigen
  // erst hier)
  import type { Component } from "svelte";
  import { holeBuch } from "../../lib/api/books";
  import { formatName } from "../../lib/format";
  import { ladeLesefassung, type Lesefassung, type Lesewahl } from "../../lib/leser/lesefassung";
  import { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { leseziel, type Leseziel } from "../../lib/leser/ziel";
  import { navigate, route } from "../../lib/router.svelte";
  import { geraet } from "../../lib/stand/geraet.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { BuchEinzeln } from "../../lib/typen";

  type Formatleser = Component<{ buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void }>;

  let { params }: { params: Record<string, string> } = $props();

  const epub = () => import("./EpubLeser.svelte");
  const text = () => import("./TextLeser.svelte");
  const leser: Record<string, () => Promise<{ default: Formatleser }>> = { pdf: () => import("./PdfLeser.svelte"), epub, mobi: epub, txt: text, md: text, bild: () => import("./Bildleser.svelte") };

  let id = $derived(Number(params.id));
  let buch = $state<BuchEinzeln | null>(null);
  let fassung = $state<Lesefassung | null>(null);
  let fehler = $state("");
  let sitzung = $derived(buch && fassung ? new Lesesitzung(buch, fassung) : null);
  async function lade(nummer: number, sprache: string | undefined, wahl: Lesewahl) {
    fehler = "";
    buch = null;
    fassung = null;
    try {
      const b = await holeBuch(nummer);
      fassung = await ladeLesefassung(b, sprache, wahl);
      buch = b;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade(id, params.sprache, { format: params.format, material: params.mid }));

  $effect(() => {
    void sitzung?.laden();
    return () => sitzung?.beende();
  });

  $effect(() => () => {
    vorlesen.halt();
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
    <Zustand art="fehler" text={fehler} onerneut={() => void lade(id, params.sprache, { format: params.format, material: params.mid })}><Knopf text="Zur Buchseite" symbol="arrow-left" klein href="/book/{id}" /></Zustand>
  </div>
{:else if buch && sitzung}
  {@const hole = leser[sitzung.fassung.format]}
  {#if hole}
    {#key `${route.path}?${route.qs}`}
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
      <Zustand text="{formatName(sitzung.fassung.format)} lässt sich hier nicht lesen."><Knopf text="Zur Buchseite" symbol="arrow-left" klein href="/book/{id}" /></Zustand>
    </div>
  {/if}
{:else}
  <div class="lesehinweis"><Zustand art="laedt" text="Buch wird geladen" /></div>
{/if}
