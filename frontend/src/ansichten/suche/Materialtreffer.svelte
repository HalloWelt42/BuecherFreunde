<script lang="ts">
  // Ein Treffer im Begleitmaterial (BF-81): nennt das Buch und die Datei, bei einem PDF die Seite; der Sprung öffnet die
  // Stelle im Material in der App
  import { ersteMarkierung } from "../../lib/auszug";
  import { zahl } from "../../lib/format";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Materialtreffer } from "../../lib/typen";
  import Trefferkarte from "./Trefferkarte.svelte";

  let { treffer, frage }: { treffer: Materialtreffer; frage: string } = $props();
  let begriff = $derived(ersteMarkierung(treffer.auszug) || frage);
  let ziel = $derived.by(() => {
    const p = new URLSearchParams();
    if (treffer.seite) p.set("page", String(treffer.seite));
    if (begriff) p.set("q", begriff);
    return `/book/${treffer.buch_id}/material/${encodeURIComponent(treffer.material_id)}?${p}`;
  });
  let ort = $derived(`Begleitmaterial ${treffer.name}${treffer.seite ? `, Seite ${zahl(treffer.seite)}` : ""}`);
</script>

<Trefferkarte buch={treffer.buch_id} titel={treffer.titel} autor={treffer.autor} deckblatt={treffer.deckblatt} {ort} symbol="paperclip" ton="info" wort="im Material">
  {#if treffer.auszug}<p class="zitat"><Auszug text={treffer.auszug} /></p>{/if}
  {#snippet knopf()}<Knopf text={treffer.seite ? `Seite ${zahl(treffer.seite)}` : "Öffnen"} symbol="book-open" klein href={ziel} />{/snippet}
</Trefferkarte>
