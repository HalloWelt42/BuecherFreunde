<script lang="ts">
  // Ein Buch auf dem Glasboden
  import { formatName, groesse, zahl } from "../../lib/format";
  import { leseAdresse, lesestand } from "../../lib/lesestand";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { merkmale } from "../../lib/stand/merkmale.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";
  import { beimKlick } from "./oeffnen";
  import { kontext } from "../../lib/stand/kontextmenue.svelte";
  import { buchmenue } from "./buchmenue";

  let { buch, gross = false, ongross = undefined }: { buch: Buch; gross?: boolean; ongross?: (buch: Buch | null, an?: HTMLElement) => void } = $props();

  let stand = $derived(lesestand(buch));
  let gewaehlt = $derived(auswahl.bearbeiten ? auswahl.hat(buch.id) : wahl.buch?.id === buch.id);
  let einzelheiten = $derived([buch.year, buch.page_count ? `${zahl(buch.page_count)} Seiten` : "", groesse(buch.file_size)].filter(Boolean).join(", "));
  let regale = $derived(buch.categories.slice(0, 2).map((c) => c.name).join(", ") + (buch.categories.length > 2 ? `, ${buch.categories.length - 2} weitere` : ""));
  let hinweis = $derived([buch.title, buch.author, einzelheiten, regale, buch.isbn ? `ISBN ${buch.isbn}` : ""].filter(Boolean).join("\n"));
</script>

{#snippet inhalt()}
  <span class="stand"><Umschlag {buch} /></span>
  <span class="boden"></span>
  <span class="schild">
    <b>{buch.title}</b>
    <span class="wer"><span>{buch.author}</span><span>{formatName(buch.file_format)}</span></span>
    {#if gross}
      <span class="mehr">
        <span class="reihe eng"><Sterne wert={buch.rating} />{#if buch.is_favorite}<Symbol name="heart" />{/if}{#if buch.is_to_read}<Symbol name="couch" />{/if}</span>
        <span class="leise zahl">{einzelheiten}</span>
        {#if regale}<span class="leise">{regale}</span>{/if}
        {#if buch.isbn}<span class="leise zahl">ISBN {buch.isbn}</span>{/if}
      </span>
    {/if}
    {#if stand.angefangen && stand.anteil < 1}<Balken anteil={stand.anteil} name="Lesestand" />{/if}
  </span>
{/snippet}

<div class="band" class:gewaehlt data-buch={buch.id} role="presentation" use:kontext={buchmenue(buch)} onpointerenter={(e) => e.pointerType === "mouse" && ongross?.(buch, e.currentTarget)} onpointerleave={() => ongross?.(null)}>
  {#if auswahl.bearbeiten}
    <button type="button" class="flaeche" aria-pressed={gewaehlt} aria-label={buch.title} onclick={() => auswahl.schalte(buch.id)}>
      <span class="haken"><Symbol name="check" /></span>{@render inhalt()}
    </button>
  {:else}
    <a class="flaeche" href="/book/{buch.id}" aria-current={gewaehlt ? "true" : undefined} aria-label={buch.title} title={ongross ? undefined : hinweis} draggable="false" onclick={(e) => beimKlick(e, buch)}>{@render inhalt()}</a>
    <span class="schnell">
      <button type="button" aria-pressed={buch.is_favorite} aria-label="Favorit" title="Favorit" onclick={() => void merkmale.favorit(buch)}><Symbol name="heart" /></button>
      <a href={leseAdresse(buch.id)} aria-label="Lesen" title="Lesen"><Symbol name="book-open" /></a>
    </span>
  {/if}
</div>
