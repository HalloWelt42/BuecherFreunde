<script lang="ts">
  import { stationsnamen, type Annahmezeile } from "../../lib/annahme/zeilen";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { annahme } from "../../lib/stand/annahme.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Aufnahmezeile from "./Aufnahmezeile.svelte";

  let { zeilen, onwaehlen }: { zeilen: Annahmezeile[]; onwaehlen: () => void } = $props();
  let stationen = $derived(stationsnamen(anschluesse.jetzt));
  let mitFertigen = $derived(annahme.zeilen.some((z) => z.gruppe === "fertig" || z.gruppe === "da" || z.wort === "Ohne Text"));

  async function blendeAus() {
    try {
      await annahme.blendeAus();
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

<section>
  <div class="titelzeile">
    <h2>Aufnahmen</h2><span class="leise">{["", "", "", "", "", "fünf", "sechs"][stationen.length]} Stationen je Datei</span><span class="schiebt"></span>
    <Knopf text="Fertige ausblenden" symbol="broom" klein frei gesperrt={!mitFertigen} titel="Nur ausgeblendet, im Verlauf bleibt alles" onclick={() => void blendeAus()} />
  </div>
  {#if annahme.grund}
    <Zustand art="fehler" text="Die Annahme antwortet nicht: {annahme.grund}" onerneut={() => void annahme.starte()} />
  {:else if !zeilen.length}
    <Zustand text={annahme.zeilen.length ? "Hier steht gerade nichts." : "Noch keine Aufnahme."} />
  {:else}
    <div class="platte">
      <div class="aufnahme kopf-aufnahme"><span></span><span></span><div class="stationen"><div class="legende">{#each stationen as s (s)}<span>{s}</span>{/each}</div></div><span></span></div>
      {#each zeilen as zeile (zeile.schluessel)}<Aufnahmezeile {zeile} {onwaehlen} />{/each}
    </div>
  {/if}
</section>

<style>
  .kopf-aufnahme {
    padding-block: 0.375rem 0;
  }
</style>
