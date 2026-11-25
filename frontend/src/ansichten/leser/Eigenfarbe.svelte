<script lang="ts">
  // Freie Farbe über Ton, Kraft und Helligkeit oder als Hex-Wert
  import { alsHex, hexZuTon, tonZuHex, type Farbton } from "../../lib/farbton";
  import Regler from "../../lib/teile/Regler.svelte";
  let { name, wert, onwahl }: { name: string; wert: string; onwahl: (hex: string) => void } = $props();
  let offen = $state(false);
  let ton = $derived(hexZuTon(wert));
  const setze = (neu: Partial<Farbton>) => onwahl(tonZuHex({ ...ton, ...neu }));

  function tippe(roh: string) {
    const hex = alsHex(roh);
    if (hex) onwahl(hex);
  }
</script>

<div class="eigen">
  <div class="reihe">
    <button type="button" class="probe" style:background={wert} aria-label="{name} wählen" title="{name} wählen" aria-expanded={offen} onclick={() => (offen = !offen)}></button>
    <span class="name">{name}</span>
    <input class="eingabe hex" aria-label="{name} als Hex-Wert" value={wert} maxlength="7" spellcheck="false" onchange={(e) => tippe(e.currentTarget.value)} />
  </div>
  {#if offen}
    <Regler name="Farbton" von={0} bis={360} wert={ton.ton} onwahl={(w) => setze({ ton: w })} />
    <Regler name="Kraft" von={0} bis={100} wert={ton.saettigung} anzeige="{ton.saettigung} %" onwahl={(w) => setze({ saettigung: w })} />
    <Regler name="Helligkeit" von={0} bis={100} wert={ton.helligkeit} anzeige="{ton.helligkeit} %" onwahl={(w) => setze({ helligkeit: w })} />
  {/if}
</div>

<style>
  .eigen {
    display: grid;
    gap: 0.375rem;
    width: 100%;
  }
  .probe {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: var(--r2);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.3);
  }
  .name {
    flex: 1;
  }
  .hex {
    width: 6.5rem;
  }
</style>
