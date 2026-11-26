<script lang="ts">
  // Was ein Kind sieht: ganze Kategorien als Chips (das Kreuz nimmt sie nach Rückfrage zurück, "+ Kategorie" wählt aus dem
  // Katalog) und einzelne Bücher über das Zuordnen in zwei Spalten. Nichts geht von selbst frei.
  import { gibFrei, ladeFreigaben, nimmFreigabe, type Freigaben, type Profil } from "../../../lib/api/familie";
  import { anzahl } from "../../../lib/format";
  import { GRAUTON, findeKategorie } from "../../../lib/katalog";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { frage } from "../../../lib/stand/rueckfrage.svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Kategoriewahl from "../../../lib/teile/Kategoriewahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { Katalogkategorie } from "../../../lib/typen";

  let { profil }: { profil: Profil } = $props();

  let freigaben = $state<Freigaben | null>(null);
  let fehler = $state("");
  let wahlOffen = $state(false);
  let knopf = $state<HTMLElement | null>(null);
  let darf = $derived(ich.darfFreigeben(profil));

  async function laden() {
    try {
      freigaben = await ladeFreigaben(profil.id);
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void laden());

  /** Farbe des Bereichs aus dem Katalog; der Server schickt nur das Zeichen */
  const farbe = (id: number) => {
    const fund = findeKategorie(bestand.katalog, id);
    return fund?.kategorie.farbe || fund?.bereich.farbe || GRAUTON;
  };

  async function tun(was: () => Promise<unknown>, gut: string) {
    try {
      await was();
      melde.gut(gut);
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
    }
    await laden();
  }

  function gib(k: Katalogkategorie) {
    wahlOffen = false;
    if (k.id !== undefined) void tun(() => gibFrei(profil.id, "kategorie", [k.id!]), `${k.name} für ${profil.name} freigegeben`);
  }

  async function nimm(k: { id: number; name: string; anzahl: number }) {
    const ja = await frage({
      titel: `${k.name} für ${profil.name} zurücknehmen?`,
      folgen: [`${profil.name} sieht ${anzahl(k.anzahl, "Buch", "Bücher")} aus ${k.name} danach nicht mehr, außer einzeln freigegebene.`, "Die Bücher selbst bleiben in der Bibliothek."],
      ja: "Zurücknehmen",
      symbol: "xmark",
    });
    if (ja) await tun(() => nimmFreigabe(profil.id, "kategorie", [k.id]), `${k.name} zurückgenommen`);
  }
</script>

<section class="elternfeld platte">
  <h3><Symbol name="book-open-reader" />Freigegeben</h3>
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  {#if freigaben}
    <div class="freigabechips">
      {#each freigaben.kategorien as k (k.id)}
        <Chip titel="{k.name}, {anzahl(k.anzahl, 'Buch', 'Bücher')}">
          <Katalogzeichen name={k.zeichen} farbe={farbe(k.id)} groesse="klein" />{k.name}
          {#if darf}<button type="button" class="heraus" aria-label="{k.name} zurücknehmen" title="{k.name} zurücknehmen" onclick={() => void nimm(k)}><Symbol name="xmark" /></button>{/if}
        </Chip>
      {/each}
      <Chip symbol="book" text={anzahl(freigaben.buecher.length, "einzelnes Buch", "einzelne Bücher")} />
      {#if darf && bestand.katalog?.hat_katalog}
        <span class="anker" bind:this={knopf}><Chip text="Kategorie" symbol="plus" gedrueckt={wahlOffen} onclick={() => (wahlOffen = !wahlOffen)} /></span>
      {/if}
    </div>
  {:else if !fehler}<p class="leise">Wird geladen</p>{/if}
  <div class="reihe">
    {#if darf}<Knopf text="Bücher zuordnen" symbol="right-left" klein href="/zuordnen/freigabe/{profil.id}" />{/if}
    <span class="hinweis">Altersangaben der Quellen stehen als Hilfe dabei.</span>
  </div>
</section>

{#if wahlOffen && bestand.katalog}
  <Menue anker={knopf} name="Kategorie freigeben" onschliessen={() => (wahlOffen = false)}>
    <Kategoriewahl bereiche={bestand.katalog.bereiche} ohne={freigaben?.kategorien.map((k) => k.id) ?? []} onwahl={gib} />
  </Menue>
{/if}

<style>
  .anker {
    display: inline-flex;
    max-width: 100%;
  }
</style>
