<script lang="ts">
  // Farbe wählen: 24 feste Töne, dazu jede eigene über Hexwert oder Regler
  import { alsHex, hexZuTon, tonZuHex, type Farbton } from "../farbton";
  import Regler from "./Regler.svelte";

  let { wert, onwahl }: { wert: string; onwahl: (farbe: string) => void } = $props();

  const toene = [
    "#ef4444", "#f43f5e", "#ec4899", "#d946ef", "#a855f7", "#8b5cf6", "#6366f1", "#3b82f6", "#0ea5e9", "#06b6d4", "#14b8a6", "#10b981",
    "#22c55e", "#84cc16", "#eab308", "#f59e0b", "#f97316", "#fb923c", "#78716c", "#a8a29e", "#6b7280", "#9ca3af", "#374151", "#111827",
  ];

  let ton = $derived(hexZuTon(wert));
  let eingabe = $state("");
  let ungueltig = $derived(eingabe !== "" && !alsHex(eingabe));

  function tippt() {
    const farbe = alsHex(eingabe);
    if (farbe) onwahl(farbe);
  }

  const setze = (neu: Partial<Farbton>) => {
    eingabe = "";
    onwahl(tonZuHex({ ...ton, ...neu }));
  };
</script>

<div class="farbwahl">
  <div class="toene" role="group" aria-label="Farben">
    {#each toene as farbe (farbe)}
      <button type="button" style:background={farbe} aria-label="Farbe {farbe}" aria-pressed={wert.toLowerCase() === farbe} title={farbe} onclick={() => { eingabe = ""; onwahl(farbe); }}></button>
    {/each}
  </div>
  <div class="eigene">
    <span class="probe" style:background={wert}></span>
    <input class="eingabe" class:ungueltig aria-label="Eigene Farbe als Hexwert" placeholder={wert} maxlength="7" spellcheck="false" bind:value={eingabe} oninput={tippt} />
  </div>
  <Regler name="Farbton" wert={ton.ton} von={0} bis={360} onwahl={(w) => setze({ ton: w })} />
  <div class="zwei">
    <Regler name="Sättigung" wert={ton.saettigung} von={0} bis={100} anzeige="{ton.saettigung} %" onwahl={(w) => setze({ saettigung: w })} />
    <Regler name="Helligkeit" wert={ton.helligkeit} von={0} bis={100} anzeige="{ton.helligkeit} %" onwahl={(w) => setze({ helligkeit: w })} />
  </div>
</div>

<style>
  .farbwahl {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .toene {
    display: grid;
    gap: 0.25rem;
    grid-template-columns: repeat(auto-fill, minmax(2rem, 1fr));
  }
  .toene button {
    height: 2rem;
    border-radius: var(--r1);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.25);
  }
  .toene button[aria-pressed="true"] {
    box-shadow:
      0 0 0 2px rgb(var(--glas)),
      0 0 0 4px var(--messing);
  }
  .eigene {
    display: grid;
    grid-template-columns: 2.25rem minmax(0, 1fr);
    gap: 0.5rem;
  }
  .probe {
    border-radius: var(--r2);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.25);
  }
  .ungueltig {
    color: var(--schlecht);
  }
  .zwei {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(auto-fit, minmax(min(9rem, 100%), 1fr));
  }
</style>
