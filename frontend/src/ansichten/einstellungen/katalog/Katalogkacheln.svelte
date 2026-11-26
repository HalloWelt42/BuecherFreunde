<script lang="ts">
  // Der Entwurf oder der gültige Katalog als Bereichskacheln im Raster (BF-69), mit Legende der Herkunft. Antippen bearbeitet
  // im Fenster, Kategorien lassen sich zwischen Bereichen ziehen.
  import { legende } from "../../../lib/katalog";
  import { arten } from "../../../lib/stand/arten.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { Katalogbereich } from "../../../lib/typen";
  import Bereichsfenster from "./Bereichsfenster.svelte";
  import Bereichskachel from "./Bereichskachel.svelte";
  import Kategoriefenster from "./Kategoriefenster.svelte";
  import { pflege, type Kategoriestelle } from "./pflege.svelte";

  let bereichOffen = $state<Katalogbereich | "neu" | null>(null);
  /** Eine Kategorie bearbeiten oder in einem Bereich neu anlegen */
  let kategorieOffen = $state<{ stelle: Kategoriestelle | null; bereich: Katalogbereich } | null>(null);
  let gezogen = $state<Kategoriestelle | null>(null);
  let ueber = $state("");
  let nimmt = $state(false);

  let istEntwurf = $derived(!!pflege.entwurf);

  // Namen der Arten für "gilt für" an den Kacheln
  $effect(() => void arten.laden());
  let zeichenerklaerung = $derived(legende(pflege.bereiche));

  async function annehmen() {
    nimmt = true;
    await pflege.annehmen();
    nimmt = false;
  }

  function ablegen(ziel: Katalogbereich) {
    const g = gezogen;
    gezogen = null;
    ueber = "";
    if (g) void pflege.verschiebe(g, ziel);
  }
</script>

<Karte titel={istEntwurf ? "Vorschlag für deinen Bestand" : "Katalog"} symbol="layer-group" breit id="katalog">
  <div class="katalog-legende">{#each zeichenerklaerung as [symbol, text] (text)}<span><Symbol name={symbol} />{text}</span>{/each}</div>
  <div class="reihe katalogtasten">
    {#if istEntwurf}<Knopf text="Vorschlag annehmen" symbol="check" haupt laeuft={nimmt} gesperrt={!pflege.bereiche.length} onclick={() => void annehmen()} />{/if}
    <Knopf text="Bereich" symbol="plus" onclick={() => (bereichOffen = "neu")} />
    {#if istEntwurf}<Knopf text="Verwerfen" symbol="xmark" frei onclick={() => void pflege.verwerfen()} />{/if}
    <span class="leise">Antippen zum Bearbeiten, Kategorien zwischen Bereichen ziehen.</span>
  </div>
  {#if pflege.bereiche.length}
    <div class="katalogkacheln">
      {#each pflege.bereiche as b (b.schluessel)}
        <Bereichskachel
          bereich={b}
          ziel={!!gezogen && ueber === b.schluessel && gezogen.bereich.schluessel !== b.schluessel}
          onbereich={() => (bereichOffen = b)}
          onkategorie={(k) => (kategorieOffen = { stelle: { kategorie: k, bereich: b }, bereich: b })}
          onneu={() => (kategorieOffen = { stelle: null, bereich: b })}
          onziehen={(k) => (gezogen = k ? { kategorie: k, bereich: b } : null)}
          onueber={(an) => (ueber = an ? b.schluessel : ueber === b.schluessel ? "" : ueber)}
          onablegen={() => ablegen(b)}
        />
      {/each}
    </div>
  {:else}<p class="leise">Noch kein Bereich.</p>{/if}
</Karte>

{#if bereichOffen}<Bereichsfenster bereich={bereichOffen === "neu" ? null : bereichOffen} onschliessen={() => (bereichOffen = null)} />{/if}
{#if kategorieOffen}<Kategoriefenster stelle={kategorieOffen.stelle} bereich={kategorieOffen.bereich} onschliessen={() => (kategorieOffen = null)} />{/if}
