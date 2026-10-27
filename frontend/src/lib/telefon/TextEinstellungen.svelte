<script>
  // Einstellfeld der Leser am Telefon (Knopf "Aa"): Schriftgröße in feinen Stufen, Schriftart, Zeilenabstand,
  // Farbthema. Jede Änderung wirkt sofort auf den Text dahinter. Was eingestellt und wo es gemerkt wird, liefert die
  // Darstellung des jeweiligen Lesers:
  //   groesse, zeilenabstand, schriftart (Kennung), themaIndex (-1: eigene Farben), schriftarten [{kennung, name,
  //   familie}], setzeGroesse(n), setzeZeilenabstand(n), setzeSchriftart(kennung), setzeThema(index)
  import { readerFarbThemen } from "../constants/themes.js";
  import { SCHRIFTGROESSE, ZEILENABSTAND } from "./lesedarstellung.js";

  let { darstellung, onSchliessen = () => {} } = $props();
</script>

<button class="hintergrund" aria-label="Einstellungen schließen" onclick={onSchliessen}></button>
<div class="feld" role="dialog" aria-label="Darstellung der Textansicht">
  <div class="kopf">
    <span>Darstellung</span>
    <button class="zu" onclick={onSchliessen} aria-label="Schließen"><i class="fa-solid fa-xmark"></i></button>
  </div>

  <div class="zeile">
    <span class="etikett">Größe</span>
    <div class="regler">
      <button onclick={() => darstellung.setzeGroesse(darstellung.groesse - SCHRIFTGROESSE.schritt)} disabled={darstellung.groesse <= SCHRIFTGROESSE.min}
        aria-label="Schrift kleiner"><i class="fa-solid fa-font" style="font-size: 0.75em"></i></button>
      <input type="range" min={SCHRIFTGROESSE.min} max={SCHRIFTGROESSE.max} step={SCHRIFTGROESSE.schritt}
        value={darstellung.groesse} oninput={(e) => darstellung.setzeGroesse(Number(e.currentTarget.value))}
        aria-label="Schriftgröße" />
      <button onclick={() => darstellung.setzeGroesse(darstellung.groesse + SCHRIFTGROESSE.schritt)} disabled={darstellung.groesse >= SCHRIFTGROESSE.max}
        aria-label="Schrift größer"><i class="fa-solid fa-font" style="font-size: 1.25em"></i></button>
      <span class="wert">{darstellung.groesse} %</span>
    </div>
  </div>

  <div class="zeile">
    <span class="etikett">Schrift</span>
    <div class="auswahl">
      {#each darstellung.schriftarten as s (s.kennung)}
        <button class="chip" class:aktiv={darstellung.schriftart === s.kennung} style:font-family={s.familie}
          onclick={() => darstellung.setzeSchriftart(s.kennung)}>{s.name}</button>
      {/each}
    </div>
  </div>

  <div class="zeile">
    <span class="etikett">Zeilen</span>
    <div class="regler">
      <button onclick={() => darstellung.setzeZeilenabstand(darstellung.zeilenabstand - ZEILENABSTAND.schritt)}
        disabled={darstellung.zeilenabstand <= ZEILENABSTAND.min} aria-label="Zeilen enger">
        <i class="fa-solid fa-minus"></i></button>
      <input type="range" min={ZEILENABSTAND.min} max={ZEILENABSTAND.max} step={ZEILENABSTAND.schritt}
        value={darstellung.zeilenabstand} oninput={(e) => darstellung.setzeZeilenabstand(Number(e.currentTarget.value))}
        aria-label="Zeilenabstand" />
      <button onclick={() => darstellung.setzeZeilenabstand(darstellung.zeilenabstand + ZEILENABSTAND.schritt)}
        disabled={darstellung.zeilenabstand >= ZEILENABSTAND.max} aria-label="Zeilen weiter">
        <i class="fa-solid fa-plus"></i></button>
      <span class="wert">{darstellung.zeilenabstand.toFixed(1)}</span>
    </div>
  </div>

  <div class="zeile">
    <span class="etikett">Farbe</span>
    <div class="auswahl">
      {#each readerFarbThemen as t, i (t.name)}
        <button class="thema" class:aktiv={darstellung.themaIndex === i} style:background-color={t.bg}
          style:color={t.fg} onclick={() => darstellung.setzeThema(i)} aria-label="Farbthema {t.name}">Aa</button>
      {/each}
    </div>
  </div>
</div>

<style>
  .hintergrund {
    position: fixed;
    inset: 0;
    z-index: 60;
    border: none;
    background: rgba(0, 0, 0, 0.25);
  }

  .feld {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 61;
    max-height: 75vh;
    overflow-y: auto;
    padding: 0.5rem 1rem 1rem;
    border-radius: 16px 16px 0 0;
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    box-shadow: 0 -6px 24px rgba(0, 0, 0, 0.3);
    font-size: 16px;
  }

  .kopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
    font-size: 17px;
  }

  .zu {
    width: 44px;
    height: 44px;
    border: none;
    background: none;
    color: inherit;
    font-size: 1.125rem;
  }

  .zeile {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    padding: 0.625rem 0;
    border-top: 1px solid var(--color-border);
  }

  .etikett {
    font-size: 15px;
    color: var(--color-text-secondary);
  }

  .regler {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .regler button {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg-primary);
    color: inherit;
    font-size: 1.0625rem;
  }

  .regler button:disabled {
    opacity: 0.35;
  }

  .regler input {
    flex: 1;
    min-width: 0;
    accent-color: var(--color-accent);
    height: 32px;
  }

  .wert {
    flex-shrink: 0;
    min-width: 3.75rem;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .auswahl {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .chip {
    min-height: 44px;
    padding: 0 0.875rem;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg-primary);
    color: inherit;
    font-size: 17px;
  }

  .chip.aktiv,
  .thema.aktiv {
    outline: 2px solid var(--color-accent);
    outline-offset: 1px;
  }

  .thema {
    width: 52px;
    height: 44px;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    font-family: Georgia, serif;
    font-size: 18px;
  }
</style>
