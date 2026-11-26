<script lang="ts">
  // Ebene der Codestellen über einer PDF-Seite (BF-29): Rechtecke aus dem Server (Punkte der Seite, oben links) mal Maß der
  // Anzeige. Die Taste sitzt auf der oberen Kante des ersten Teils, rechts, damit sie nie den Kastentitel deckt; jeder
  // weitere Teil trägt die Marke der Fortsetzung. Ist das Listing im Fenster offen, markiert ein Streifen links alle Teile.
  // Steht über der Taste Text der Seite zu nah, sitzt sie innen am oberen Rand (BF-55): gemessen an der Textebene, sobald
  // pdf.js sie gezeichnet hat, in Punkten der Seite, damit es beim Zoomen gilt.
  import type { Codestelle } from "../../lib/api/ausfuehren";
  import { luftUeber } from "../../lib/leser/text/codeorte";
  import { ausfuehren } from "../../lib/stand/ausfuehren.svelte";
  import Codetaste from "./Codetaste.svelte";

  let { buch, nr, stellen, mass, seitenname, onoeffne }: { buch: number; nr: number; stellen: Codestelle[]; mass: number; seitenname: (nr: number) => string; onoeffne: (s: Codestelle) => void } = $props();

  /** Freier Platz über der Taste je Teil, in Punkten der Seite; fehlt er, gilt die Kante */
  let luft = $state<Record<string, number>>({});

  function misst(kasten: HTMLElement, schluessel: string) {
    const seite = kasten.closest(".pdfseite");
    if (!seite) return;
    const rechne = () => {
      const taste = kasten.querySelector(".codetaste")?.getBoundingClientRect();
      const zeilen = [...seite.querySelectorAll(".textLayer span")].map((e) => e.getBoundingClientRect());
      if (!taste || !zeilen.length) return;
      const l = luftUeber({ top: kasten.getBoundingClientRect().top, left: taste.left, right: taste.right }, zeilen);
      const wert = Number.isFinite(l) ? l / mass : Number.POSITIVE_INFINITY;
      if (luft[schluessel] !== wert) luft[schluessel] = wert;
    };
    const beobachter = new MutationObserver(rechne);
    beobachter.observe(seite, { childList: true, subtree: true });
    rechne();
    return { destroy: () => beobachter.disconnect() };
  }
  const luftVon = (schluessel: string) => (Number.isFinite(luft[schluessel] ?? Number.POSITIVE_INFINITY) ? `${luft[schluessel] * mass}px` : undefined);
</script>

{#each stellen as s (s.kennung)}
  {#each s.teile as t, k (k)}
    {#if t.seite === nr && t.rechteck}
      {@const [x0, y0, x1, y1] = t.rechteck}
      <div class="codestelle" class:offen={ausfuehren.istOffen(buch, s.kennung)} class:oben-offen={t.offen_oben} class:unten-offen={t.offen_unten} style:--x0={x0} style:--y0={y0} style:--x1={x1} style:--y1={y1} style:--mass={mass} style:--luft={luftVon(`${s.kennung}-${k}`)} use:misst={`${s.kennung}-${k}`}>
        <Codetaste stelle={s} weiterVon={k > 0 ? seitenname(s.teile[0].seite ?? nr) : ""} onoeffne={() => onoeffne(s)} />
      </div>
    {/if}
  {/each}
{/each}
