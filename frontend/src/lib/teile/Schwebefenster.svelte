<script lang="ts">
  // Frei verschiebbares Fenster wie ein Notizzettel: am Kopf ziehen, an der Ecke die Größe ändern; Ort und Größe bleiben im
  // Browser gemerkt. Am Telefon hat es einen festen Platz unten.
  import type { Snippet } from "svelte";
  import { beiEsc } from "../flucht";
  import { liesJson, merkeJson } from "../speicher";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "./Knopf.svelte";
  import Symbol from "./Symbol.svelte";

  interface Ort {
    x: number;
    y: number;
    w: number;
    h: number;
  }
  interface Eigenschaften {
    /** Unter diesem Namen ist der Ort gemerkt */
    merkname: string;
    titel: string;
    symbol: string;
    /** Versatz gegenüber der Ecke unten rechts, damit mehrere Fenster nicht aufeinander liegen */
    stufe?: number;
    klasse?: string;
    zusatz?: Snippet;
    knoepfe?: Snippet;
    onschliessen: () => void;
    children: Snippet;
  }
  let { merkname, titel, symbol, stufe = 0, klasse = "", zusatz, knoepfe, onschliessen, children }: Eigenschaften = $props();

  const MIND_B = 220;
  const MIND_H = 140;
  let fenster: HTMLElement | undefined = $state();
  let zieht = $state(false);
  let gemerkt = $state<Ort | null>(null);

  $effect.pre(() => {
    gemerkt = liesJson<Ort | null>(merkname, null);
    schale.fensterVorn = merkname;
  });
  const nachVorn = () => (schale.fensterVorn = merkname);
  $effect(() => beiEsc(() => onschliessen()));

  let ort = $derived(schale.telefon ? null : gemerkt);
  const klemme = (w: number, bis: number) => Math.max(4, Math.min(Math.max(4, bis - 4), w));

  function bewege(e: PointerEvent, rechne: (dx: number, dy: number, r: DOMRect, p: DOMRect) => Ort) {
    if (!fenster || schale.telefon) return;
    const r = fenster.getBoundingClientRect();
    const p = fenster.parentElement!.getBoundingClientRect();
    const [x0, y0] = [e.clientX, e.clientY];
    const griff = e.currentTarget as HTMLElement;
    griff.setPointerCapture(e.pointerId);
    zieht = true;
    const weiter = (m: PointerEvent) => (gemerkt = rechne(m.clientX - x0, m.clientY - y0, r, p));
    const ende = () => {
      zieht = false;
      griff.removeEventListener("pointermove", weiter);
      if (gemerkt) merkeJson(merkname, gemerkt);
    };
    griff.addEventListener("pointermove", weiter);
    griff.addEventListener("pointerup", ende, { once: true });
    griff.addEventListener("pointercancel", ende, { once: true });
  }

  function verschiebe(e: PointerEvent) {
    if ((e.target as Element).closest("button, a, input")) return;
    bewege(e, (dx, dy, r, p) => ({ x: klemme(r.left - p.left + dx, p.width - r.width), y: klemme(r.top - p.top + dy, p.height - r.height), w: r.width, h: r.height }));
  }

  function aendereGroesse(e: PointerEvent) {
    bewege(e, (dx, dy, r, p) => ({ x: r.left - p.left, y: r.top - p.top, w: Math.max(MIND_B, Math.min(p.width - 8, r.width + dx)), h: Math.max(MIND_H, Math.min(p.height - 8, r.height + dy)) }));
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<section
  class="schwebefenster glas dicht {klasse}"
  aria-label={titel}
  bind:this={fenster}
  onpointerdown={nachVorn}
  style:--stufe={stufe}
  class:vorn={schale.fensterVorn === merkname}
  style:left={ort ? `${ort.x}px` : undefined}
  style:top={ort ? `${ort.y}px` : undefined}
  style:right={ort ? "auto" : undefined}
  style:bottom={ort ? "auto" : undefined}
  style:width={ort ? `${ort.w}px` : undefined}
  style:height={ort ? `${ort.h}px` : undefined}
>
  <header class:zieht onpointerdown={verschiebe}>
    <Symbol name={symbol} /><span class="name">{titel}</span>
    {@render zusatz?.()}
    <span class="schiebt reihe eng">
      {@render knoepfe?.()}
      <Knopf text="Schließen" symbol="xmark" nur klein frei onclick={onschliessen} />
    </span>
  </header>
  {@render children()}
  <span class="griff" title="Größe ändern" onpointerdown={aendereGroesse}></span>
</section>

<style>
  .name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .eng {
    gap: 0;
    flex-wrap: nowrap;
  }
  .griff {
    position: absolute;
    right: 0;
    bottom: 0;
    width: 1.25rem;
    height: 1.25rem;
    cursor: nwse-resize;
    touch-action: none;
    background: linear-gradient(135deg, transparent 55%, rgb(var(--kante) / 0.7) 55% 62%, transparent 62% 74%, rgb(var(--kante) / 0.7) 74% 81%, transparent 81%);
  }
</style>
