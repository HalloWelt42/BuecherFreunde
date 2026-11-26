<script lang="ts">
  // Ein Bild aus dem Begleitmaterial in der App (BF-81): ins Fenster eingepasst, ein Tippen zeigt es in voller Größe zum
  // Verschieben, noch eins passt es wieder ein. Oben wie in jedem Leser zurück, der Name und Herunterladen.
  import type { Leseziel } from "../../lib/leser/ziel";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { BuchEinzeln } from "../../lib/typen";

  let { buch, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  let fassung = $derived(sitzung.fassung);
  let name = $derived(fassung.dateiname === true ? buch.title : fassung.dateiname);
  let titel = $derived(fassung.titel ?? name);
  let ganz = $state(false);
  let kaputt = $state(false);
</script>

<div class="leser bildleser">
  <div class="leseleiste oben glas klar">
    <Knopf text="Zurück" symbol="arrow-left" nur frei klein onclick={onzurueck} />
    <b title={titel}>{titel}</b>
    <Knopf text="Herunterladen" symbol="download" nur frei klein href={fassung.anhang} download={name} />
  </div>
  {#if kaputt}
    <div class="seiten"><Zustand art="fehler" text="Das Bild ließ sich nicht laden."><Knopf text="Herunterladen" symbol="download" klein href={fassung.anhang} download={name} /></Zustand></div>
  {:else}
    <button type="button" class="bildflaeche" class:ganz aria-label={ganz ? "Einpassen" : "In voller Größe zeigen"} title={ganz ? "Einpassen" : "In voller Größe zeigen"} onclick={() => (ganz = !ganz)}>
      <img src={fassung.datei} alt={name} draggable="false" onerror={() => (kaputt = true)} />
    </button>
  {/if}
</div>

<style>
  .bildflaeche {
    min-height: 0;
    overflow: auto;
    display: grid;
    place-items: center;
    padding: 4rem var(--rand-seite) 1rem;
    cursor: zoom-in;
  }
  .bildflaeche img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: var(--r1);
    box-shadow: 0 0 0 1px var(--linie), 0 8px 24px -12px rgb(var(--schatten) / 0.6);
  }
  .bildflaeche.ganz {
    place-items: start;
    cursor: zoom-out;
  }
  .bildflaeche.ganz img {
    max-width: none;
    max-height: none;
  }
</style>
