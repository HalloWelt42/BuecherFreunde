<script lang="ts">
  import { inhaltsbild } from "../../lib/inhaltsbild";
  // Abbildung bildschirmfüllend: zwei Finger oder Mausrad zoomen, einer schiebt, doppelt tippen wechselt
  import { beiEsc } from "../../lib/flucht";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let { quelle, beschreibung = "", onschliessen }: { quelle: string; beschreibung?: string; onschliessen: () => void } = $props();

  interface Punkt {
    x: number;
    y: number;
  }
  const MAX = 8;
  const DOPPELT_ZOOM = 2.5;
  const DOPPELT_MS = 300;

  let zoom = $state(1);
  let x = $state(0);
  let y = $state(0);
  const finger = new Map<number, Punkt>();
  let start: { zoom: number; x: number; y: number; punkt: Punkt; abstand: number } | null = null;
  let letztesTippen = 0;

  $effect(() => beiEsc(onschliessen));

  const begrenze = (z: number) => Math.min(MAX, Math.max(1, z));
  const mitte = (a: Punkt, b: Punkt) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

  function anDieApp(knoten: HTMLElement) {
    document.querySelector(".app")?.appendChild(knoten);
    return { destroy: () => knoten.remove() };
  }

  function geste() {
    const [a, b] = [...finger.values()];
    start = a ? { zoom, x, y, punkt: b ? mitte(a, b) : { ...a }, abstand: b ? Math.hypot(a.x - b.x, a.y - b.y) : 0 } : null;
  }

  function runter(e: PointerEvent) {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    finger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    geste();
  }

  function bewege(e: PointerEvent) {
    if (!finger.has(e.pointerId) || !start) return;
    finger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const [a, b] = [...finger.values()];
    if (b && start.abstand) {
      // Um die Fingermitte zoomen und mit ihr wandern
      const neu = begrenze(start.zoom * (Math.hypot(a.x - b.x, a.y - b.y) / start.abstand));
      const m = mitte(a, b);
      x = m.x - (start.punkt.x - start.x) * (neu / start.zoom);
      y = m.y - (start.punkt.y - start.y) * (neu / start.zoom);
      zoom = neu;
    } else if (!b && zoom > 1) {
      x = start.x + a.x - start.punkt.x;
      y = start.y + a.y - start.punkt.y;
    }
  }

  function hoch(e: PointerEvent) {
    finger.delete(e.pointerId);
    if (finger.size) return geste();
    start = null;
    if (zoom <= 1.02) zuruecksetzen();
  }

  function tippe(e: MouseEvent) {
    const jetzt = performance.now();
    if (jetzt - letztesTippen >= DOPPELT_MS) {
      letztesTippen = jetzt;
      return;
    }
    letztesTippen = 0;
    if (zoom > 1) return zuruecksetzen();
    // Um die getippte Stelle; die Verschiebung zählt ab der Mitte der Fläche
    const f = (e.currentTarget as HTMLElement).getBoundingClientRect();
    zoom = DOPPELT_ZOOM;
    x = -(e.clientX - f.left - f.width / 2) * (DOPPELT_ZOOM - 1);
    y = -(e.clientY - f.top - f.height / 2) * (DOPPELT_ZOOM - 1);
  }

  function zuruecksetzen() {
    [zoom, x, y] = [1, 0, 0];
  }

  function stufe(faktor: number) {
    const neu = begrenze(zoom * faktor);
    [x, y, zoom] = [(x * neu) / zoom, (y * neu) / zoom, neu];
    if (zoom === 1) zuruecksetzen();
  }
</script>

<div class="lupe" role="dialog" aria-modal="true" aria-label={beschreibung || "Abbildung vergrößert"} use:anDieApp>
  <div class="flaeche" role="presentation" onpointerdown={runter} onpointermove={bewege} onpointerup={hoch} onpointercancel={hoch} onclick={tippe} onwheel={(e) => stufe(e.deltaY < 0 ? 1.15 : 1 / 1.15)}>
    <img src={quelle} alt={beschreibung} draggable="false" use:inhaltsbild style:transform="translate({x}px, {y}px) scale({zoom})" />
  </div>
  <div class="knoepfe reihe">
    <Knopf text="Verkleinern" symbol="magnifying-glass-minus" nur gesperrt={zoom <= 1} onclick={() => stufe(1 / 1.5)} />
    <Knopf text="Vergrößern" symbol="magnifying-glass-plus" nur gesperrt={zoom >= MAX} onclick={() => stufe(1.5)} />
    <Knopf text="Schließen" symbol="xmark" nur onclick={onschliessen} />
  </div>
  {#if beschreibung}<p>{beschreibung}</p>{/if}
</div>

<style>
  .lupe {
    position: absolute;
    inset: 0;
    z-index: 80;
    background: rgb(6 12 11 / 0.95);
    color: #fff;
    display: grid;
    grid-template-rows: minmax(0, 1fr) auto;
  }
  .flaeche {
    display: grid;
    place-items: center;
    overflow: hidden;
    touch-action: none;
    cursor: grab;
  }
  .flaeche img {
    max-width: 100%;
    max-height: 100%;
    background: #fff;
    will-change: transform;
    user-select: none;
  }
  .knoepfe {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    --tinte: #fff;
    --knopf: rgb(255 255 255 / 0.16);
    --knopf-auf: rgb(255 255 255 / 0.28);
  }
  p {
    padding: 0.75rem 1rem 1rem;
    text-align: center;
  }
</style>
