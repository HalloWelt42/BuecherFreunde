<script lang="ts">
  import { zahl } from "../../lib/format";
  import { leseAdresse } from "../../lib/lesestand";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Bedeutungstreffer } from "../../lib/typen";
  import Trefferkarte from "./Trefferkarte.svelte";

  let { treffer }: { treffer: Bedeutungstreffer } = $props();
  // Ein Stück Wortlaut genügt dem Leser, um die Stelle auf der Seite zu finden
  const STUECK = 80;
  let ort = $derived([treffer.seite ? `Seite ${zahl(treffer.seite)}` : "", treffer.gedruckt ? `gedruckt ${treffer.gedruckt}` : ""].filter(Boolean).join(", "));
</script>

<Trefferkarte buch={treffer.buch_id} titel={treffer.titel} autor={treffer.autor} deckblatt={treffer.deckblatt} {ort} symbol="brain" ton="gut" wort={treffer.naehe}>
  <p class="zitat">{treffer.auszug}</p>
  {#snippet knopf()}<Knopf text={treffer.seite ? `Seite ${zahl(treffer.seite)}` : "Lesen"} symbol="book-open" klein href={leseAdresse(treffer.buch_id, { page: treffer.seite ?? undefined, stelle: treffer.auszug.slice(0, STUECK) })} />{/snippet}
</Trefferkarte>
