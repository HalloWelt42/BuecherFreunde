<script lang="ts">
  // PIN aus Ziffern (BF-78) als großes Zahlenfeld: 1 bis 9, Zurück, 0, Fertig. Die Tastatur geht ebenso (Ziffern, Rücktaste,
  // Eingabe). Ein neuer `versuch` (etwa nach einer falschen PIN) leert die Stellen und schüttelt sie kurz.
  import type { Zugang } from "../api/familie";
  import { pinGueltig } from "../familie";
  import { untrack } from "svelte";
  import Symbol from "./Symbol.svelte";

  let { zugang, onfertig, gesperrt = false, versuch = 0, name = "PIN" }: { zugang: Zugang; onfertig: (pin: string) => void; gesperrt?: boolean; versuch?: number; name?: string } = $props();
  let von = $derived(zugang.pin_stellen_von);
  let bis = $derived(zugang.pin_stellen_bis);

  let pin = $state("");
  let schuettelt = $state(false);
  /** Mindestens so viele Stellen wie nötig; ab da eine freie mehr, bis die längste PIN erreicht ist */
  let stellen = $derived(Math.max(von, Math.min(bis, pin.length + (pin.length >= von && pin.length < bis ? 1 : 0))));

  // Nur ein neuer Versuch zählt, nicht der, mit dem das Feld erscheint
  let gezaehlt = untrack(() => versuch);
  $effect(() => {
    if (versuch === gezaehlt) return;
    gezaehlt = versuch;
    pin = "";
    schuettelt = true;
    const uhr = setTimeout(() => (schuettelt = false), 500);
    return () => clearTimeout(uhr);
  });

  function ziffer(z: string) {
    if (!gesperrt && pin.length < bis) pin += z;
  }

  function weg() {
    if (!gesperrt) pin = pin.slice(0, -1);
  }

  function fertig() {
    if (!gesperrt && pinGueltig(pin, zugang)) onfertig(pin);
  }

  function taste(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    // Wer in ein Feld oder ein Fenster tippt (etwa PIN vergessen), meint nicht das Zahlenfeld
    if (e.target instanceof Element && e.target.closest("input, textarea, select, [contenteditable], dialog")) return;
    if (/^\d$/.test(e.key)) ziffer(e.key);
    else if (e.key === "Backspace") weg();
    else if (e.key === "Enter") fertig();
    else return;
    e.preventDefault();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="zahlenpin" role="group" aria-label={name}>
  <div class="plaetze" class:schuettelt aria-live="polite" aria-label="{pin.length} von mindestens {von} Ziffern">
    {#each { length: stellen } as _, n (n)}<span class="platz" class:voll={n < pin.length}></span>{/each}
  </div>
  <div class="tastenfeld">
    {#each ["1", "2", "3", "4", "5", "6", "7", "8", "9"] as z (z)}
      <button type="button" class="taste" disabled={gesperrt} onclick={() => ziffer(z)}>{z}</button>
    {/each}
    <button type="button" class="taste" aria-label="Letzte Ziffer löschen" title="Letzte Ziffer löschen" disabled={gesperrt || !pin} onclick={weg}><Symbol name="delete-left" /></button>
    <button type="button" class="taste" disabled={gesperrt} onclick={() => ziffer("0")}>0</button>
    <button type="button" class="taste haupt" aria-label="Fertig" title="Fertig" disabled={gesperrt || !pinGueltig(pin, zugang)} onclick={fertig}><Symbol name="check" /></button>
  </div>
</div>

<style>
  .zahlenpin {
    display: grid;
    justify-items: center;
    gap: var(--pin-abstand, 1rem);
  }
  .plaetze {
    display: flex;
    gap: calc(var(--pin-taste, 3.25rem) * 0.2);
    min-height: calc(var(--pin-taste, 3.25rem) * 0.36);
    align-items: center;
  }
  .platz {
    width: calc(var(--pin-taste, 3.25rem) * 0.3);
    height: calc(var(--pin-taste, 3.25rem) * 0.3);
    border-radius: 50%;
    border: 0.1875rem solid var(--pin-linie, var(--linie));
  }
  .platz.voll {
    border-color: var(--pin-haupt, var(--messing));
    background: var(--pin-haupt, var(--messing));
  }
  .tastenfeld {
    display: grid;
    grid-template-columns: repeat(3, var(--pin-taste, 3.25rem));
    gap: calc(var(--pin-taste, 3.25rem) * 0.16);
  }
  .taste {
    height: var(--pin-taste, 3.25rem);
    display: grid;
    place-items: center;
    border-radius: var(--pin-ecke, var(--r2));
    background: var(--pin-flaeche, var(--knopf));
    color: var(--pin-tinte, var(--tinte));
    box-shadow: 0 0.25rem 0 var(--pin-linie, var(--linie)), inset 0 0 0 0.15rem var(--pin-linie, var(--linie));
    font-size: calc(var(--pin-taste, 3.25rem) * 0.4);
    font-weight: 700;
    font-family: inherit;
  }
  .taste.haupt {
    background: var(--pin-haupt, var(--messing-flaeche));
    color: #fff;
    box-shadow: 0 0.25rem 0 color-mix(in srgb, var(--pin-haupt, var(--messing-flaeche)) 60%, #000);
  }
  .taste:active:not(:disabled) {
    transform: translateY(0.125rem);
  }
  .taste:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .schuettelt {
    animation: schuetteln 0.45s ease-in-out;
  }
  .schuettelt .platz {
    border-color: var(--schlecht);
  }
  @keyframes schuetteln {
    20%, 60% { transform: translateX(-0.5rem); }
    40%, 80% { transform: translateX(0.5rem); }
  }
  @media (prefers-reduced-motion: reduce) {
    .schuettelt {
      animation: none;
    }
  }
</style>
