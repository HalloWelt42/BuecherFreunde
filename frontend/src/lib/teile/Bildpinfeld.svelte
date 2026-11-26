<script lang="ts">
  // Bild-PIN (BF-78): drei von neun Bildern antippen. Oben die drei Stellen, ein Tipp auf eine volle Stelle nimmt sie und
  // alle danach zurück. Sind drei gewählt, geht die Folge an `onvoll`. Ein neuer `versuch` (etwa nach einer falschen
  // Bild-PIN) leert die Stellen und schüttelt sie kurz: Fehler zeigen statt schreiben.
  import { BILDER, BILDPIN_LAENGE, bildName, bildSymbol } from "../familie";
  import { untrack } from "svelte";
  import Symbol from "./Symbol.svelte";

  let { onvoll, gesperrt = false, versuch = 0, name = "Bild-PIN" }: { onvoll: (bilder: string[]) => void; gesperrt?: boolean; versuch?: number; name?: string } = $props();

  let bilder = $state<string[]>([]);
  let schuettelt = $state(false);

  // Nur ein neuer Versuch zählt, nicht der, mit dem das Feld erscheint
  let gezaehlt = untrack(() => versuch);
  $effect(() => {
    if (versuch === gezaehlt) return;
    gezaehlt = versuch;
    bilder = [];
    schuettelt = true;
    const uhr = setTimeout(() => (schuettelt = false), 500);
    return () => clearTimeout(uhr);
  });

  function tippe(schluessel: string) {
    if (gesperrt || bilder.length >= BILDPIN_LAENGE) return;
    bilder = [...bilder, schluessel];
    if (bilder.length === BILDPIN_LAENGE) onvoll([...bilder]);
  }

  /** Eine Stelle zurück, samt allen danach */
  function zurueck(stelle: number) {
    if (!gesperrt) bilder = bilder.slice(0, stelle);
  }

  /** Von außen leeren, etwa nach dem Speichern */
  export function leere(): void {
    bilder = [];
  }
</script>

<div class="bildpin" role="group" aria-label={name}>
  <div class="plaetze" class:schuettelt aria-live="polite">
    {#each { length: BILDPIN_LAENGE } as _, n (n)}
      {@const b = bilder[n]}
      {#if b}
        <button type="button" class="platz voll" aria-label="{n + 1}. Bild: {bildName(b)}, zurücknehmen" disabled={gesperrt} onclick={() => zurueck(n)}><Symbol name={bildSymbol(b)} /></button>
      {:else}
        <span class="platz" aria-label="{n + 1}. Bild fehlt"></span>
      {/if}
    {/each}
  </div>
  <div class="tastenfeld">
    {#each BILDER as [schluessel, symbol, wort] (schluessel)}
      <button type="button" class="taste" aria-label={wort} title={wort} disabled={gesperrt || bilder.length >= BILDPIN_LAENGE} onclick={() => tippe(schluessel)}><Symbol name={symbol} /></button>
    {/each}
  </div>
</div>

<style>
  /* Maße und Farben kommen von der Umgebung: groß und kindgerecht bei "Wer liest?", knapper im Fenster */
  .bildpin {
    display: grid;
    justify-items: center;
    gap: var(--pin-abstand, 1rem);
  }
  .plaetze {
    display: flex;
    gap: calc(var(--pin-taste, 3.25rem) * 0.2);
  }
  .platz {
    width: calc(var(--pin-taste, 3.25rem) * 0.75);
    height: calc(var(--pin-taste, 3.25rem) * 0.75);
    border-radius: var(--pin-ecke, var(--r2));
    border: 0.1875rem dashed var(--pin-linie, var(--linie));
    display: grid;
    place-items: center;
    font-size: calc(var(--pin-taste, 3.25rem) * 0.36);
    color: inherit;
  }
  .platz.voll {
    border-style: solid;
    border-color: var(--pin-haupt, var(--messing));
    color: var(--pin-haupt, var(--messing));
    background: var(--pin-flaeche, var(--platte));
    cursor: pointer;
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
    font-size: calc(var(--pin-taste, 3.25rem) * 0.46);
  }
  .taste:active:not(:disabled) {
    transform: translateY(0.125rem);
    box-shadow: 0 0.125rem 0 var(--pin-linie, var(--linie)), inset 0 0 0 0.15rem var(--pin-linie, var(--linie));
  }
  .taste:disabled {
    opacity: 0.6;
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
