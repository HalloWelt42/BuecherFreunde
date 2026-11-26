<script lang="ts">
  // Tasten an den Codestellen in Markdown, Text und EPUB (BF-29): eine Ebene über dem Buch, wie die Marken am Rand. Der
  // Leser des Formats nennt die Codeblöcke auf dem Schirm mit ihrer Lage (sitzung.code); die Taste sitzt auf der oberen
  // Kante, rechts, ein späterer Teil trägt die Marke der Fortsetzung. Ist über der Taste weniger Platz frei als ihre halbe
  // Höhe, sitzt sie innen am oberen Rand (BF-55, stil/leser.css): gemessen an den Zeilen über dem Block, die sie in der
  // Waagerechten berührt, noch im selben Bild. Bei jeder Bewegung der Ansicht neu gelegt.
  import { tick } from "svelte";
  import type { Codestelle } from "../../lib/api/ausfuehren";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { luftUeber } from "../../lib/leser/text/codeorte";
  import Codetaste from "./Codetaste.svelte";

  let { sitzung, rahmen }: { sitzung: Lesesitzung; rahmen: HTMLElement } = $props();

  let orte = $state<{ stelle: Codestelle; teil: number; x: number; y: number; rechts: number; luft: number; schluessel: string }[]>([]);
  let ebene: HTMLElement | undefined = $state();
  let bild = 0;
  let lauf = 0;

  async function lege() {
    const code = sitzung.code;
    if (!code) return void (orte = []);
    const r = rahmen.getBoundingClientRect();
    const oben = (rahmen.querySelector(".leseleiste.oben")?.getBoundingClientRect().bottom ?? r.top) + 4;
    const unten = rahmen.querySelector(".leseleiste.unten")?.getBoundingClientRect().top ?? r.bottom;
    // Die linke Kante zählt: eine Spalte des Nachbarblatts im EPUB ragt sonst mit ihrem Rand herein
    const gefunden = code.orte().filter(({ lage }) => lage.width > 0 && lage.top >= oben && lage.top < unten - 20 && lage.left >= r.left && lage.left < r.right);
    const vorher = new Map(orte.map((o) => [o.schluessel, o.luft]));
    orte = gefunden.map(({ stelle, teil, lage }, n) => {
      const schluessel = `${stelle.kennung}-${teil}-${n}`;
      return { stelle, teil, x: lage.left - r.left, y: lage.top - r.top, rechts: r.right - lage.right, luft: vorher.get(schluessel) ?? Number.POSITIVE_INFINITY, schluessel };
    });
    const dieser = ++lauf;
    await tick();
    if (dieser !== lauf || !ebene) return;
    const tasten = [...ebene.querySelectorAll<HTMLElement>(":scope > .codeanker > .codetaste")];
    const luft = gefunden.map(({ lage, darueber }, n) => {
      const t = tasten[n]?.getBoundingClientRect();
      return t ? luftUeber({ top: lage.top, left: t.left, right: t.right }, darueber) : Number.POSITIVE_INFINITY;
    });
    if (luft.some((l, n) => l !== orte[n]?.luft)) orte = orte.map((o, n) => ({ ...o, luft: luft[n] ?? o.luft }));
  }

  $effect(() => {
    void [sitzung.bewegung, sitzung.code, sitzung.feld];
    cancelAnimationFrame(bild);
    bild = requestAnimationFrame(lege);
  });
  $effect(() => {
    const b = new ResizeObserver(() => {
      cancelAnimationFrame(bild);
      bild = requestAnimationFrame(lege);
    });
    b.observe(rahmen);
    return () => {
      b.disconnect();
      cancelAnimationFrame(bild);
    };
  });
  const erste = (s: Codestelle) => s.teile[0];
</script>

<div class="codetastenebene" bind:this={ebene}>
  {#each orte as o (o.schluessel)}
    <div class="codeanker" style:top="{o.y}px" style:right="{o.rechts}px" style:left="{o.x}px" style:--luft={Number.isFinite(o.luft) ? `${o.luft}px` : undefined}>
      <Codetaste stelle={o.stelle} weiterVon={o.teil > 0 ? String(erste(o.stelle).seite ?? "") : ""} onoeffne={() => sitzung.code?.oeffne(o.stelle)} />
    </div>
  {/each}
</div>

<style>
  .codetastenebene {
    position: absolute;
    inset: 0;
    z-index: 4;
    pointer-events: none;
    overflow: hidden;
  }
  .codeanker {
    position: absolute;
    height: 0;
  }
  /* Rechts oben im Block steht schon "Code kopieren" */
  .codeanker :global(.codetaste) {
    right: 3rem;
  }
</style>
