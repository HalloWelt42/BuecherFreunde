<script lang="ts">
  // Ein Buch mit den gesuchten Wörtern. Seite und Zahl der Stellen holt die Karte erst, wenn sie zu sehen ist.
  import { volltextSuche } from "../../lib/api/books";
  import { ersteMarkierung } from "../../lib/auszug";
  import { anzahl, zahl } from "../../lib/format";
  import { leseAdresse } from "../../lib/lesestand";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Treffer } from "../../lib/typen";
  import Trefferkarte from "./Trefferkarte.svelte";

  let { treffer, frage }: { treffer: Treffer; frage: string } = $props();
  let stellen = $state<{ zahl: number; seite: number; prozent: number } | null>(null);
  let begriff = $derived(ersteMarkierung(treffer.snippet));

  function sobaldSichtbar(knoten: HTMLElement) {
    const b = new IntersectionObserver((e) => {
      if (!e.some((x) => x.isIntersecting)) return;
      b.disconnect();
      void hole();
    });
    b.observe(knoten);
    return { destroy: () => b.disconnect() };
  }

  async function hole() {
    if (!begriff) return;
    try {
      const a = await volltextSuche(treffer.book_id, begriff, { limit: 1 });
      if (a.gesamt) stellen = { zahl: a.gesamt, seite: a.treffer[0].seite, prozent: a.treffer[0].prozent };
    } catch {
      // ohne Zahl der Stellen bleibt der Sprung über das Suchwort
    }
  }

  let ziel = $derived(leseAdresse(treffer.book_id, { page: stellen?.seite, percent: stellen?.prozent || undefined, q: begriff || frage }));
</script>

<div use:sobaldSichtbar>
<Trefferkarte buch={treffer.book_id} titel={treffer.titel} autor={treffer.autor} ort={stellen ? `Seite ${zahl(stellen.seite)}` : ""} symbol="font" ton="info" wort={stellen ? `wörtlich, ${anzahl(stellen.zahl, "Stelle", "Stellen")}` : begriff ? "wörtlich" : "passt zum Filter"}>
  {#if treffer.snippet}<p class="zitat"><Auszug text={treffer.snippet} /></p>{/if}
  {#snippet knopf()}<Knopf text={stellen ? `Seite ${zahl(stellen.seite)}` : "Lesen"} symbol="book-open" klein href={ziel} />{/snippet}
</Trefferkarte>
</div>
