<script lang="ts">
  // Regale, Typ und Sammlung eines Buchs: antippen filtert die Bibliothek, der Stift nimmt heraus
  import { entferneBuch, ordneBuchZu } from "../../lib/api/categories";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Regalwahl from "../../lib/teile/Regalwahl.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { BuchEinzeln, Regal, RegalKurz } from "../../lib/typen";
  import { TYPEN } from "./typen";

  let { buch, ongeaendert }: { buch: BuchEinzeln; ongeaendert: () => void } = $props();

  const ZUERST = 5;
  let alle = $state(false);
  let aendern = $state(false);
  let wahlOffen = $state(false);
  let knopf = $state<HTMLElement | null>(null);

  let sichtbar = $derived(alle || aendern ? buch.categories : buch.categories.slice(0, ZUERST));
  let rest = $derived(buch.categories.length - sichtbar.length);

  async function tun(was: () => Promise<unknown>, text: string) {
    try {
      await was();
      melde.gut(text);
      bestand.geaendert();
      ongeaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
    }
  }

  const nimmHeraus = (r: RegalKurz) => tun(() => entferneBuch(r.id, buch.id), `Aus ${r.name} genommen`);

  function stelleEin(r: Regal) {
    wahlOffen = false;
    void tun(() => ordneBuchZu(r.id, buch.id), `In ${r.name} gestellt`);
  }
</script>

<div class="reihe">
  {#each sichtbar as r (r.id)}
    {#if aendern}
      <Chip text={r.name} titel="Aus diesem Regal nehmen" onclick={() => void nimmHeraus(r)}><Symbol name="xmark" /></Chip>
    {:else}
      <Chip text={r.name} titel="Bibliothek nach diesem Regal filtern" href="/?category={r.id}" />
    {/if}
  {/each}
  {#if rest > 0}<Chip text="{rest} weitere" onclick={() => (alle = true)} />{/if}
  {#if buch.typ}<Chip text={TYPEN[buch.typ] ?? buch.typ} />{/if}
  {#if buch.sammlung}<Chip text="{buch.sammlung.name}{buch.band_nummer ? `, Band ${buch.band_nummer}` : ''}" farbe={buch.sammlung.color} href="/?sammlung={buch.sammlung.id}" titel="Bibliothek nach dieser Sammlung filtern" />{/if}
  <Knopf text="Regal dazu" symbol="plus" klein frei aufgeklappt={wahlOffen} bind:element={knopf} onclick={() => (wahlOffen = !wahlOffen)} />
  {#if buch.categories.length}<Knopf text={aendern ? "Fertig" : "Regale ändern"} symbol={aendern ? "check" : "pen"} nur={!aendern} klein frei gedrueckt={aendern} onclick={() => (aendern = !aendern)} />{/if}
</div>

{#if wahlOffen}
  <Menue anker={knopf} name="Regal dazu" onschliessen={() => (wahlOffen = false)}><Regalwahl ohne={buch.categories.map((c) => c.id)} onwahl={stelleEin} /></Menue>
{/if}
