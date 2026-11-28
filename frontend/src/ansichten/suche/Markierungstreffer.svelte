<script lang="ts">
  // Ein Treffer in einer eigenen Markierung (BF-123): nennt das Buch und die Seite; der Sprung öffnet das Buch an der Stelle,
  // bei einem Rechteck einer gescannten Seite rollt der Leser es in den Blick
  import { zahl } from "../../lib/format";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Markierungstreffer } from "../../lib/typen";
  import Trefferkarte from "./Trefferkarte.svelte";

  let { treffer }: { treffer: Markierungstreffer } = $props();
  let ziel = $derived.by(() => {
    const p = new URLSearchParams();
    if (treffer.seite) p.set("page", String(treffer.seite));
    if (treffer.stelle.includes(":bereich:")) p.set("stelle", treffer.stelle);
    return `/book/${treffer.buch_id}/read?${p}`;
  });
  let ort = $derived(`Markierung${treffer.seite ? `, Seite ${zahl(treffer.seite)}` : ""}`);
</script>

<Trefferkarte buch={treffer.buch_id} titel={treffer.titel} autor={treffer.autor} deckblatt={treffer.deckblatt} {ort} symbol="highlighter" ton="info" wort="in Markierung">
  {#if treffer.auszug}<p class="zitat"><Auszug text={treffer.auszug} /></p>{/if}
  {#snippet knopf()}<Knopf text={treffer.seite ? `Seite ${zahl(treffer.seite)}` : "Öffnen"} symbol="book-open" klein href={ziel} />{/snippet}
</Trefferkarte>
