<script>
  // Abbildung bildschirmfüllend: mit zwei Fingern zoomen, mit einem verschieben, doppelt tippen wechselt zwischen
  // eingepasst und vergrößert. Bleibt offen, bis man sie schließt.
  let { quelle, beschreibung = "", onSchliessen = () => {} } = $props();

  const MIN = 1;
  const MAX = 8;
  const DOPPELT_ZOOM = 2.5;
  const DOPPELT_MS = 300;

  let zoom = $state(1);
  let x = $state(0);
  let y = $state(0);

  const finger = new Map();
  let start = null;          // Ausgangslage einer Geste
  let letztesTippen = 0;

  function begrenze(z) {
    return Math.min(MAX, Math.max(MIN, z));
  }

  function abstand(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function mitte(a, b) {
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }

  function geste() {
    const [a, b] = [...finger.values()];
    start = b
      ? { zoom, x, y, abstand: abstand(a, b), mitte: mitte(a, b) }
      : { zoom, x, y, punkt: { ...a } };
  }

  function runter(e) {
    e.currentTarget.setPointerCapture(e.pointerId);
    finger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    geste();
  }

  function bewegen(e) {
    if (!finger.has(e.pointerId) || !start) return;
    finger.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const [a, b] = [...finger.values()];
    if (b && start.abstand) {
      // um die Fingermitte zoomen und mit ihr mitwandern
      const neu = begrenze(start.zoom * (abstand(a, b) / start.abstand));
      const m = mitte(a, b);
      const faktor = neu / start.zoom;
      x = m.x - (start.mitte.x - start.x) * faktor;
      y = m.y - (start.mitte.y - start.y) * faktor;
      zoom = neu;
    } else if (!b && start.punkt && zoom > 1) {
      x = start.x + (a.x - start.punkt.x);
      y = start.y + (a.y - start.punkt.y);
    }
  }

  function hoch(e) {
    finger.delete(e.pointerId);
    if (finger.size > 0) {
      geste();
      return;
    }
    start = null;
    if (zoom <= 1.02) zuruecksetzen();
  }

  function tippen(e) {
    const jetzt = performance.now();
    if (jetzt - letztesTippen < DOPPELT_MS) {
      if (zoom > 1) {
        zuruecksetzen();
      } else {
        // um die getippte Stelle vergrößern (Ursprung der Verschiebung ist die Mitte der Fläche)
        const flaeche = e.currentTarget.getBoundingClientRect();
        const px = e.clientX - flaeche.left - flaeche.width / 2;
        const py = e.clientY - flaeche.top - flaeche.height / 2;
        zoom = DOPPELT_ZOOM;
        x = -px * (DOPPELT_ZOOM - 1);
        y = -py * (DOPPELT_ZOOM - 1);
      }
      letztesTippen = 0;
    } else {
      letztesTippen = jetzt;
    }
  }

  function zuruecksetzen() {
    zoom = 1;
    x = 0;
    y = 0;
  }

  function stufe(faktor) {
    const neu = begrenze(zoom * faktor);
    x *= neu / zoom;
    y *= neu / zoom;
    zoom = neu;
    if (zoom === 1) zuruecksetzen();
  }

  function taste(e) {
    if (e.key === "Escape") onSchliessen();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="lupe" role="dialog" aria-modal="true" aria-label={beschreibung || "Abbildung vergrößert"}>
  <div
    class="flaeche"
    role="presentation"
    onpointerdown={runter}
    onpointermove={bewegen}
    onpointerup={hoch}
    onpointercancel={hoch}
    onclick={tippen}
  >
    <img
      src={quelle}
      alt={beschreibung}
      draggable="false"
      style:transform="translate({x}px, {y}px) scale({zoom})"
    />
  </div>
  <div class="knoepfe">
    <button onclick={() => stufe(1 / 1.5)} disabled={zoom <= MIN} aria-label="Verkleinern">
      <i class="fa-solid fa-magnifying-glass-minus"></i>
    </button>
    <button onclick={() => stufe(1.5)} disabled={zoom >= MAX} aria-label="Vergrößern">
      <i class="fa-solid fa-magnifying-glass-plus"></i>
    </button>
    <button class="schliessen" onclick={onSchliessen} aria-label="Schließen">
      <i class="fa-solid fa-xmark"></i>
    </button>
  </div>
  {#if beschreibung}
    <p class="beschreibung">{beschreibung}</p>
  {/if}
</div>

<style>
  .lupe {
    position: fixed;
    inset: 0;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    background: #000;
  }

  .flaeche {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    touch-action: none;
  }

  img {
    max-width: 100%;
    max-height: 100%;
    background: #fff;
    transform-origin: center;
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
    will-change: transform;
  }

  .knoepfe {
    position: absolute;
    top: calc(0.5rem + env(safe-area-inset-top));
    right: 0.5rem;
    display: flex;
    gap: 0.5rem;
  }

  .knoepfe button {
    width: 48px;
    height: 48px;
    border: none;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.16);
    color: #fff;
    font-size: 1.125rem;
  }

  .knoepfe button:disabled {
    opacity: 0.35;
  }

  .knoepfe .schliessen {
    background: rgba(255, 255, 255, 0.3);
  }

  .beschreibung {
    flex-shrink: 0;
    max-height: 30vh;
    overflow-y: auto;
    padding: 0.75rem 1rem 1rem;
    color: #e5e7eb;
    font-size: 16px;
    line-height: 1.5;
  }
</style>
