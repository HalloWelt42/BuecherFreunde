<script lang="ts">
  import { beiEsc } from "../flucht";
  import { anzahl } from "../format";
  import { melde } from "../stand/meldungen.svelte";
  import { notizblock, type Notizort } from "../stand/notizblock.svelte";
  import { frage } from "../stand/rueckfrage.svelte";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";

  const MIND_B = 200;
  const MIND_H = 120;
  let block: HTMLElement | undefined = $state();
  let zieht = $state(false);

  // Am Telefon hat der Block einen festen Platz
  let ort = $derived<Notizort | null>(schale.telefon ? null : notizblock.ort);

  $effect(() => beiEsc(() => (schale.notizOffen = false)));

  function bewege(e: PointerEvent, rechne: (dx: number, dy: number, r: DOMRect, p: DOMRect) => Notizort) {
    if (!block || schale.telefon) return;
    const r = block.getBoundingClientRect();
    const p = block.parentElement!.getBoundingClientRect();
    const [x0, y0] = [e.clientX, e.clientY];
    const griff = e.currentTarget as HTMLElement;
    griff.setPointerCapture(e.pointerId);
    zieht = true;
    const weiter = (m: PointerEvent) => (notizblock.ort = rechne(m.clientX - x0, m.clientY - y0, r, p));
    const ende = () => {
      zieht = false;
      griff.removeEventListener("pointermove", weiter);
      if (notizblock.ort) notizblock.merkeOrt(notizblock.ort);
    };
    griff.addEventListener("pointermove", weiter);
    griff.addEventListener("pointerup", ende, { once: true });
    griff.addEventListener("pointercancel", ende, { once: true });
  }

  function verschiebe(e: PointerEvent) {
    if ((e.target as Element).closest("button")) return;
    bewege(e, (dx, dy, r, p) => ({ x: klemme(r.left - p.left + dx, p.width - r.width), y: klemme(r.top - p.top + dy, p.height - r.height), w: r.width, h: r.height }));
  }

  function aendereGroesse(e: PointerEvent) {
    bewege(e, (dx, dy, r, p) => ({ x: r.left - p.left, y: r.top - p.top, w: Math.max(MIND_B, Math.min(p.width - 8, r.width + dx)), h: Math.max(MIND_H, Math.min(p.height - 8, r.height + dy)) }));
  }

  const klemme = (w: number, bis: number) => Math.max(4, Math.min(Math.max(4, bis - 4), w));

  async function kopiere() {
    await navigator.clipboard.writeText(notizblock.text);
    melde.gut("Kopiert");
  }

  async function leere() {
    if (!notizblock.text.trim()) return;
    const ja = await frage({ titel: "Schnellnotiz leeren?", folgen: [`${anzahl(notizblock.woerter, "Wort geht", "Wörter gehen")} verloren.`], ja: "Leeren" });
    if (ja) notizblock.text = "";
  }
</script>

<section class="notizblock glas dicht" aria-label="Schnellnotiz" bind:this={block} style:left={ort ? `${ort.x}px` : undefined} style:top={ort ? `${ort.y}px` : undefined} style:right={ort ? "auto" : undefined} style:bottom={ort ? "auto" : undefined} style:width={ort ? `${ort.w}px` : undefined} style:height={ort ? `${ort.h}px` : undefined}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <header class:zieht onpointerdown={verschiebe}>
    <Symbol name="note-sticky" />Schnellnotiz
    {#if notizblock.woerter}<span class="leise zahl">{anzahl(notizblock.woerter, "Wort", "Wörter")}</span>{/if}
    <span class="schiebt reihe eng">
      <Knopf text="Alles kopieren" symbol="copy" nur klein frei onclick={kopiere} />
      <Knopf text="Leeren" symbol="trash-can" nur klein frei onclick={leere} />
      <Knopf text="Schließen" symbol="xmark" nur klein frei onclick={() => (schale.notizOffen = false)} />
    </span>
  </header>
  <textarea id="schnellnotiz" aria-label="Notiz" placeholder="Hier schreiben, gemerkt in diesem Browser" spellcheck="false" bind:value={notizblock.text}></textarea>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <span class="griff" title="Größe ändern" onpointerdown={aendereGroesse}></span>
</section>

<style>
  .eng {
    gap: 0;
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
