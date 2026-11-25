<script lang="ts">
  import { formatName, groesse, zahl } from "../../lib/format";
  import { lesestand, standText } from "../../lib/lesestand";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";
  import Grossbild from "./Grossbild.svelte";
  import { beimKlick } from "./oeffnen";
  import { ziehauswahl } from "./ziehauswahl";

  let { liste }: { liste: Buch[] } = $props();
  let gross = $state<{ buch: Buch; an: HTMLElement } | null>(null);

  function angaben(b: Buch): string {
    return [formatName(b.file_format), b.page_count ? `${zahl(b.page_count)} Seiten` : "", groesse(b.file_size), b.publisher, b.isbn ? `ISBN ${b.isbn}` : "", ...b.categories.map((c) => c.name)].filter(Boolean).join(", ");
  }
</script>

{#snippet inhalt(buch: Buch)}
  <span class="bild" role="presentation" onpointerenter={(e) => e.pointerType === "mouse" && (gross = { buch, an: e.currentTarget })} onpointerleave={() => (gross = null)}>
    {#if auswahl.bearbeiten}<span class="haken"><Symbol name="check" /></span>{/if}<Umschlag {buch} />
  </span>
  <span class="text">
    <b>{buch.title}</b><br />{[buch.author, buch.year].filter(Boolean).join(", ")}<br /><span class="leise">{angaben(buch)}</span>
    {#if lesestand(buch).angefangen}<br /><span class="leise">{standText(buch)}</span>{/if}
  </span>
  <span class="zeichen-rechts"><Sterne wert={buch.rating} /> {#if buch.is_favorite}<Symbol name="heart" />{/if} {#if buch.is_to_read}<Symbol name="couch" />{/if}</span>
{/snippet}

<div use:ziehauswahl={{ an: auswahl.bearbeiten, art: "zeilen" }}>
  {#each liste as buch (buch.id)}
    {#if auswahl.bearbeiten}
      <button type="button" class="zeile mehr" data-buch={buch.id} aria-pressed={auswahl.hat(buch.id)} onclick={() => auswahl.schalte(buch.id)}>{@render inhalt(buch)}</button>
    {:else}
      <a class="zeile mehr" data-buch={buch.id} href="/book/{buch.id}" aria-current={wahl.buch?.id === buch.id ? "true" : undefined} draggable="false" onclick={(e) => beimKlick(e, buch)}>{@render inhalt(buch)}</a>
    {/if}
  {/each}
</div>
{#if gross}<Grossbild buch={gross.buch} an={gross.an} />{/if}
