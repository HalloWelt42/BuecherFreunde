<script lang="ts">
  // Vorige oder nächste Stelle mit Notiz, Markierung oder Etikett, am Telefon in der Leiste unten (BF-63, Entwurf
  // telefonleiste, Vorschlag A). Gesperrt, wenn es in der Richtung keine gibt; nach dem Sprung klappt die Karte am Rand auf.
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { springeWeiter, ziel } from "../../lib/leser/stellensprung";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { sitzung, richtung }: { sitzung: Lesesitzung; richtung: 1 | -1 } = $props();

  let rand = $derived(sitzung.rand);
  let wohin = $derived(rand ? ziel(sitzung.stellen, rand.stand(), sitzung.gesprungen, richtung) : null);
  let name = $derived(richtung === 1 ? "Nächste Stelle" : "Vorige Stelle");
  let hinweis = $derived(wohin ? `${name}: ${wohin.eintrag.art}, ${wohin.eintrag.ort}` : `${name}: keine ${richtung === 1 ? "danach" : "davor"}`);
</script>

<button type="button" class="knopf nur frei klein stellensprung" aria-label={hinweis} title={hinweis} disabled={!wohin} onclick={() => rand && springeWeiter(sitzung, rand, sitzung.stellen, richtung)}>
  {#if richtung === -1}<Symbol name="chevron-left" klasse="pfeil" />{/if}<Symbol name="bookmark" klasse="marke" />{#if richtung === 1}<Symbol name="chevron-right" klasse="pfeil" />{/if}
</button>

<style>
  .stellensprung {
    gap: 0.1875rem;
  }
  .stellensprung :global(.marke) {
    color: var(--messing);
  }
  .stellensprung :global(.pfeil) {
    font-size: 0.75em;
  }
  .stellensprung:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
