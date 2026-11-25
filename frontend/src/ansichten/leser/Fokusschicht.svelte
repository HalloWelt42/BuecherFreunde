<script lang="ts">
  // Fokus: eine Schicht über dem Buch, außen abgedunkelt oder milchig, innen klar. Fenster (frei gezogen), Lineal (Zeilenband)
  // oder Absatz. Klicks, Auswahl und Scrollen gehen hindurch; nur beim Anpassen des Fensters lassen sich Griffe fassen.
  import { streifenUm, type Kasten } from "../../lib/leser/fokus";
  import { lesehilfen } from "../../lib/leser/lesehilfen.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";

  let { sitzung, rahmen, linealY = $bindable(null) }: { sitzung: Lesesitzung; rahmen: HTMLElement; linealY?: number | null } = $props();

  const RAND = 6;
  let f = $derived(lesehilfen.fokus);
  let flaeche = $state({ links: 0, oben: 0, breite: 0, hoehe: 0 });
  let loch = $state<Kasten | null>(null);
  let gezogen = $state<{ x: number; y: number; b: number; h: number } | null>(null);
  let takt = $state(0);
  let anpassen = $derived(f.art === "fenster" && sitzung.feld === "fokus");
  let liestHier = $derived(vorlesen.aktiv && vorlesen.quelle !== null && vorlesen.quelle === sitzung.quelle);

  // Beim Vorlesen bewegt sich die Stelle ohne eigenes Ereignis: ein ruhiger Takt
  $effect(() => {
    if (!liestHier || f.art === "fenster") return;
    const uhr = setInterval(() => takt++, 250);
    return () => clearInterval(uhr);
  });

  function rechne(): Kasten | null {
    const r = rahmen.getBoundingClientRect();
    flaeche = { links: r.left, oben: r.top, breite: r.width, hoehe: r.height };
    const h = sitzung.hilfe;
    if (f.art === "fenster") {
      const w = gezogen ?? f.fenster;
      return { links: (w.x - w.b / 2) * r.width, oben: (w.y - w.h / 2) * r.height, rechts: (w.x + w.b / 2) * r.width, unten: (w.y + w.h / 2) * r.height };
    }
    if (!h) return null;
    const blatt = h.blatt() ?? r;
    const [links, rechts] = [blatt.left - r.left, blatt.right - r.left];
    if (f.art === "lineal") {
      const zeile = h.zeilenhoehe();
      const v = liestHier ? h.vorgelesen().zeile : null;
      const mitte = v ? (v.oben + v.unten) / 2 : (linealY ?? (sitzung.zeiger?.y ?? r.top + r.height / 3));
      const halb = (f.zeilen * zeile) / 2;
      return { links, oben: mitte - r.top - halb, rechts, unten: mitte - r.top + halb };
    }
    const a = liestHier ? h.vorgelesen().absatz : sitzung.zeiger ? h.absatzBei(sitzung.zeiger.x, sitzung.zeiger.y) : null;
    if (!a) return loch;
    return { links: a.links - r.left - RAND, oben: a.oben - r.top - RAND, rechts: a.rechts - r.left + RAND, unten: a.unten - r.top + RAND };
  }

  $effect(() => {
    void [sitzung.zeiger, sitzung.bewegung, takt, f, gezogen, linealY, liestHier, sitzung.hilfe];
    loch = rechne();
  });
  $effect(() => {
    const b = new ResizeObserver(() => (loch = rechne()));
    b.observe(rahmen);
    return () => b.disconnect();
  });

  let streifen = $derived(loch ? streifenUm(loch, flaeche.breite, flaeche.hoehe, f.verlauf) : []);

  // Anpassen: innen fassen verschiebt, an Kanten und Ecken ändert die Größe; Doppelklick stellt zurück
  function fasse(e: PointerEvent, kante: string) {
    e.preventDefault();
    const start = { x: e.clientX, y: e.clientY, w: { ...f.fenster } };
    const ziel = e.currentTarget as HTMLElement;
    ziel.setPointerCapture(e.pointerId);
    const grenze = (wert: number, min: number, max: number) => Math.min(max, Math.max(min, wert));
    const zieh = (m: PointerEvent) => {
      const dx = (m.clientX - start.x) / flaeche.breite;
      const dy = (m.clientY - start.y) / flaeche.hoehe;
      const w = { ...start.w };
      if (kante === "mitte") [w.x, w.y] = [grenze(w.x + dx, w.b / 2, 1 - w.b / 2), grenze(w.y + dy, w.h / 2, 1 - w.h / 2)];
      if (kante.includes("o")) [w.y, w.h] = [w.y + dy / 2, grenze(w.h - dy, 0.08, 1)];
      if (kante.includes("u")) [w.y, w.h] = [w.y + dy / 2, grenze(w.h + dy, 0.08, 1)];
      if (kante.includes("l")) [w.x, w.b] = [w.x + dx / 2, grenze(w.b - dx, 0.1, 1)];
      if (kante.includes("r")) [w.x, w.b] = [w.x + dx / 2, grenze(w.b + dx, 0.1, 1)];
      gezogen = w;
    };
    const los = () => {
      ziel.removeEventListener("pointermove", zieh);
      if (gezogen) lesehilfen.setzeFokus({ fenster: gezogen });
      gezogen = null;
    };
    ziel.addEventListener("pointermove", zieh);
    ziel.addEventListener("pointerup", los, { once: true });
    ziel.addEventListener("pointercancel", los, { once: true });
  }
  const zuruecksetzen = () => lesehilfen.setzeFokus({ fenster: { x: 0.5, y: 0.45, b: 0.6, h: 0.5 } });
  const KANTEN = ["o", "u", "l", "r", "ol", "or", "ul", "ur"];
</script>

{#if loch}
  <div class="fokus" class:milchig={f.huelle === "milchig"} class:zieht={!!gezogen} aria-hidden="true" style:--fokusfarbe={f.farbe} style:--deckung="{Math.round(f.staerke * 100)}%" style:--verlauf="{f.verlauf}px">
    {#each streifen as s (s.rand)}
      <i class="streifen {s.rand}" style:left="{s.links}px" style:top="{s.oben}px" style:width="{s.breite}px" style:height="{s.hoehe}px"></i>
    {/each}
    {#if anpassen}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="griff" style:left="{loch.links}px" style:top="{loch.oben}px" style:width="{loch.rechts - loch.links}px" style:height="{loch.unten - loch.oben}px" onpointerdown={(e) => fasse(e, "mitte")} ondblclick={zuruecksetzen}>
        {#each KANTEN as k (k)}<span class="kante {k}" onpointerdown={(e) => (e.stopPropagation(), fasse(e, k))}></span>{/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .fokus {
    position: absolute;
    inset: 0;
    z-index: 3;
    pointer-events: none;
    overflow: hidden;
  }
  .streifen {
    position: absolute;
    background: color-mix(in srgb, var(--fokusfarbe) var(--deckung), transparent);
    transition: top 0.12s ease-out, left 0.12s ease-out, width 0.12s ease-out, height 0.12s ease-out;
  }
  .zieht .streifen {
    transition: none;
  }
  /* Milchig: ein Hauch Papier mit wenig Unschärfe, nicht die ganze Seite weich gerechnet */
  .milchig .streifen {
    background: color-mix(in srgb, var(--randgrund, #fff) var(--deckung), transparent);
    -webkit-backdrop-filter: blur(2px);
    backdrop-filter: blur(2px);
  }
  .streifen.unten {
    mask-image: linear-gradient(to bottom, #000 calc(100% - var(--verlauf)), transparent);
  }
  .streifen.oben {
    mask-image: linear-gradient(to top, #000 calc(100% - var(--verlauf)), transparent);
  }
  .streifen.rechts {
    mask-image: linear-gradient(to right, #000 calc(100% - var(--verlauf)), transparent);
  }
  .streifen.links {
    mask-image: linear-gradient(to left, #000 calc(100% - var(--verlauf)), transparent);
  }
  .griff {
    position: absolute;
    pointer-events: auto;
    cursor: move;
    outline: 1px dashed color-mix(in srgb, var(--randtinte, #000) 55%, transparent);
    outline-offset: -1px;
    touch-action: none;
  }
  .kante {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 3px;
    background: var(--messing);
    box-shadow: 0 0 0 2px rgb(255 255 255 / 0.8);
  }
  .kante.o, .kante.u { left: calc(50% - 7px); cursor: ns-resize; }
  .kante.l, .kante.r { top: calc(50% - 7px); cursor: ew-resize; }
  .kante.o, .kante.ol, .kante.or { top: -7px; }
  .kante.u, .kante.ul, .kante.ur { bottom: -7px; }
  .kante.l, .kante.ol, .kante.ul { left: -7px; }
  .kante.r, .kante.or, .kante.ur { right: -7px; }
  .kante.ol, .kante.ur { cursor: nwse-resize; }
  .kante.or, .kante.ul { cursor: nesw-resize; }
  .kante.ol, .kante.ur, .kante.or, .kante.ul { width: 12px; height: 12px; }
  @media (prefers-reduced-motion: reduce) {
    .streifen {
      transition: none;
    }
  }
</style>
