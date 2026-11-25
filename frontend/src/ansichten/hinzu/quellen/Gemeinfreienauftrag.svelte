<script lang="ts">
  // Laufende oder letzte Übernahme gemeinfreier Bücher
  import type { Uebernahmestand } from "../../../lib/api/gutenberg";
  import { zahl } from "../../../lib/format";
  import { gutenberg } from "../../../lib/stand/gutenberg.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { stand }: { stand: Uebernahmestand } = $props();
  const lagen: Record<string, [string, string]> = { ok: ["circle-check", "gut"], duplikat: ["clone", "info"], fehler: ["circle-xmark", "schlecht"] };

  async function zurueck() {
    try {
      await gutenberg.zuruecksetzen();
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

<section class="mulde auftrag" aria-live="polite">
  <div class="reihe">
    <b>{stand.laeuft ? "Wird geholt" : "Fertig geholt"}</b>
    <span class="leise zahl">{zahl(stand.fertig)} von {zahl(stand.gesamt)}{stand.duplikate ? `, ${zahl(stand.duplikate)} gab es schon` : ""}{stand.fehler ? `, ${zahl(stand.fehler)} gescheitert` : ""}</span>
    {#if !stand.laeuft}<span class="schiebt"><Knopf text="Zurücksetzen" symbol="broom" klein frei onclick={() => void zurueck()} /></span>{/if}
  </div>
  <Balken anteil={stand.gesamt ? stand.fertig / stand.gesamt : 0} gut={!stand.laeuft} name="Gemeinfreie Bücher holen" />
  {#if stand.laeuft && stand.aktuell}<span class="leise">{stand.aktuell}</span>{/if}
  {#if stand.ergebnisse.length}
    <ul>
      {#each stand.ergebnisse as e, n (n)}
        {@const [symbol, ton] = lagen[e.status] ?? lagen.fehler}
        <li><span class="marke-text {ton}"><Symbol name={symbol} /></span>{#if e.book_id}<a href="/book/{e.book_id}">{e.titel}</a>{:else}<span>{e.titel}</span>{/if}<span class="leise">{e.detail}</span></li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .auftrag {
    display: grid;
    gap: 0.5rem;
    padding: 0.625rem 0.75rem;
  }
  ul {
    display: grid;
    max-height: 14rem;
    overflow: auto;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.125rem 0.5rem;
    padding: 0.25rem 0;
    overflow-wrap: anywhere;
  }
</style>
