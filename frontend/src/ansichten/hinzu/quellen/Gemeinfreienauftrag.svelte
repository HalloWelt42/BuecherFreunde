<script lang="ts">
  // Laufende oder letzte Übernahme gemeinfreier Bücher: die Einträge der Annahme mit Quelle gemeinfrei
  import type { Sammellage, Sammelstand } from "../../../lib/annahme/sammlung";
  import { zahl } from "../../../lib/format";
  import { gutenberg } from "../../../lib/stand/gutenberg.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { stand }: { stand: Sammelstand } = $props();
  const lagen: Record<Sammellage, [string, string]> = { fertig: ["circle-check", "gut"], da: ["clone", "info"], fehler: ["circle-xmark", "schlecht"], laeuft: ["circle-notch", "info"], wartet: ["hourglass-half", "info"] };
  const titel = (name: string) => name.replace(/\.(?:epub|txt)$/, "");
  let ergebnisse = $derived(stand.eintraege.filter((e) => ["fertig", "da", "fehler"].includes(stand.lagen.get(e.id) ?? "")));

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
    <span class="leise zahl">{zahl(stand.erledigt)} von {zahl(stand.gesamt)}{stand.da ? `, ${zahl(stand.da)} gab es schon` : ""}{stand.gescheitert ? `, ${zahl(stand.gescheitert)} gescheitert` : ""}</span>
    {#if !stand.laeuft}<span class="schiebt"><Knopf text="Zurücksetzen" symbol="broom" klein frei onclick={() => void zurueck()} /></span>{/if}
  </div>
  <Balken anteil={stand.gesamt ? stand.erledigt / stand.gesamt : 0} gut={!stand.laeuft} name="Gemeinfreie Bücher holen" />
  {#if stand.aktuell}<span class="leise">{titel(stand.aktuell.name)}: {stand.aktuell.text}</span>{/if}
  {#if ergebnisse.length}
    <ul>
      {#each ergebnisse as e (e.id)}
        {@const [symbol, ton] = lagen[stand.lagen.get(e.id) ?? "fehler"]}
        <li><span class="marke-text {ton}"><Symbol name={symbol} /></span>{#if e.buch_id}<a href="/book/{e.buch_id}">{titel(e.name)}</a>{:else}<span>{titel(e.name)}</span>{/if}<span class="leise">{e.text}</span></li>
      {/each}
    </ul>
  {/if}
</section>

<style>
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
