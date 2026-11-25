<script lang="ts">
  // Freie Farbe über Ton, Kraft und Helligkeit oder als Hex-Wert
  import { hexZuHsl, hslZuHex } from "../../lib/leser/farben";
  import Regler from "../../lib/teile/Regler.svelte";
  let { name, wert, onwahl }: { name: string; wert: string; onwahl: (hex: string) => void } = $props();
  let offen = $state(false);
  let hsl = $derived(hexZuHsl(wert));
  const setze = (neu: Partial<typeof hsl>) => onwahl(hslZuHex({ ...hsl, ...neu }));

  function tippe(roh: string) {
    const hex = roh.trim().startsWith("#") ? roh.trim() : `#${roh.trim()}`;
    if (/^#[0-9a-f]{6}$/i.test(hex)) onwahl(hex.toLowerCase());
  }
</script>

<div class="eigen">
  <div class="reihe">
    <button type="button" class="probe" style:background={wert} aria-label="{name} wählen" title="{name} wählen" aria-expanded={offen} onclick={() => (offen = !offen)}></button>
    <span class="name">{name}</span>
    <input class="eingabe hex" aria-label="{name} als Hex-Wert" value={wert} maxlength="7" spellcheck="false" onchange={(e) => tippe(e.currentTarget.value)} />
  </div>
  {#if offen}
    <Regler name="Farbton" von={0} bis={360} wert={hsl.h} onwahl={(h) => setze({ h })} />
    <Regler name="Kraft" von={0} bis={100} wert={hsl.s} anzeige="{hsl.s} %" onwahl={(s) => setze({ s })} />
    <Regler name="Helligkeit" von={0} bis={100} wert={hsl.l} anzeige="{hsl.l} %" onwahl={(l) => setze({ l })} />
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
