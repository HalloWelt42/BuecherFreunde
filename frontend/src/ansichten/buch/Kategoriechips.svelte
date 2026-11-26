<script lang="ts">
  // Kategorien des Katalogs an einem Buch (BF-69): Chips mit Zeichen und Farbe des Bereichs, antippen filtert die Bibliothek,
  // das Kreuz nimmt das Buch nach Rückfrage heraus, "+ Kategorie" wählt aus dem Katalog
  import { entferneBuch, ordneBuchZu } from "../../lib/api/categories";
  import { GRAUTON, findeKategorie, trenneKategorien } from "../../lib/katalog";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Katalogzeichen from "../../lib/teile/Katalogzeichen.svelte";
  import Kategoriewahl from "../../lib/teile/Kategoriewahl.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { BuchEinzeln, Katalogbereich, Katalogkategorie, RegalKurz } from "../../lib/typen";

  let { buch, ongeaendert }: { buch: BuchEinzeln; ongeaendert: () => void } = $props();

  let wahlOffen = $state(false);
  let knopf = $state<HTMLElement | null>(null);
  let kategorien = $derived(trenneKategorien(buch.categories, bestand.katalog).kategorien);

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

  async function nimmHeraus(k: RegalKurz) {
    const ja = await frage({
      titel: `Aus ${k.name} nehmen?`,
      folgen: [`${buch.title} steht danach nicht mehr in ${k.name}${k.bereich ? ` (${k.bereich})` : ""}.`, "Die Kategorie selbst bleibt."],
      ja: "Herausnehmen",
      symbol: "xmark",
    });
    if (ja) await tun(() => entferneBuch(k.id, buch.id), `Aus ${k.name} genommen`);
  }

  function stelleEin(k: Katalogkategorie, b: Katalogbereich) {
    wahlOffen = false;
    if (k.id !== undefined) void tun(() => ordneBuchZu(k.id!, buch.id), `In ${k.name} (${b.name}) eingeordnet`);
  }

  /** Zeichen und Farbe liefert der Server am Buch; fehlen sie, steht der Katalog dafür ein */
  function zeichenVon(k: RegalKurz): { zeichen: string; farbe: string } {
    const fund = findeKategorie(bestand.katalog, k.id);
    return { zeichen: k.zeichen || fund?.kategorie.zeichen || "", farbe: k.farbe || fund?.kategorie.farbe || fund?.bereich.farbe || GRAUTON };
  }
</script>

{#if bestand.katalog?.hat_katalog || kategorien.length}
  <div class="reihe kategoriechips">
    {#each kategorien as k (k.id)}
      {@const z = zeichenVon(k)}
      <Chip>
        <a class="kategoriename" href="/?category={k.id}" title="Bibliothek nach {k.name} filtern"><Katalogzeichen name={z.zeichen} farbe={z.farbe} groesse="klein" />{k.name}</a>
        <button type="button" class="heraus" aria-label="Aus {k.name} nehmen" title="Aus {k.name} nehmen" onclick={() => void nimmHeraus(k)}><Symbol name="xmark" /></button>
      </Chip>
    {/each}
    {#if bestand.katalog?.hat_katalog}
      <span class="anker" bind:this={knopf}><Chip text="Kategorie" symbol="plus" gedrueckt={wahlOffen} onclick={() => (wahlOffen = !wahlOffen)} /></span>
    {/if}
  </div>
{/if}

{#if wahlOffen && bestand.katalog}
  <Menue anker={knopf} name="Kategorie wählen" onschliessen={() => (wahlOffen = false)}>
    <Kategoriewahl bereiche={bestand.katalog.bereiche} ohne={kategorien.map((k) => k.id)} onwahl={stelleEin} />
  </Menue>
{/if}

<style>
  .anker {
    display: inline-flex;
    max-width: 100%;
  }
  .kategoriename {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    color: inherit;
    text-decoration: none;
    min-width: 0;
  }
  .kategoriename:hover {
    color: var(--tinte);
  }
  .heraus {
    display: inline-grid;
    place-items: center;
    color: var(--tinte-3);
    min-width: 1.25rem;
    align-self: stretch;
  }
  .heraus:hover {
    color: var(--tinte);
  }
</style>
