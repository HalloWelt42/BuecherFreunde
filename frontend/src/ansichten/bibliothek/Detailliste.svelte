<script lang="ts">
  import { formatName, groesse, zahl } from "../../lib/format";
  import { lesestand, standText } from "../../lib/lesestand";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import { eintragsschluessel } from "../../lib/stand/eintraege";
  import type { Buch, Eintrag, Sammlungseintrag } from "../../lib/typen";
  import Grossbild from "./Grossbild.svelte";
  import { baende, sammlungshinweis, sammlungsweg } from "./sammlungseintrag";
  import Stapel from "./Stapel.svelte";
  import { beimKlick } from "./oeffnen";
  import { kontext } from "../../lib/stand/kontextmenue.svelte";
  import { buchmenue } from "./buchmenue";
  import { ziehauswahl } from "./ziehauswahl";

  let { eintraege }: { eintraege: Eintrag[] } = $props();
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

<!-- Eine Sammlung ist kein Buch (BF-66): eine Zeile zum Öffnen, auch im Bearbeitungsmodus nicht anhakbar -->
{#snippet sammlungszeile(s: Sammlungseintrag)}
  <a class="zeile mehr" data-sammlung={s.id} href={sammlungsweg(s.id)} title={sammlungshinweis(s)} draggable="false">
    <span class="bild"><Stapel sammlung={s} /></span>
    <span class="text"><b>{s.name}</b><br />{s.autor}<br /><span class="leise">Sammlung, {baende(s.anzahl)}</span></span>
    <span class="zeichen-rechts"></span>
  </a>
{/snippet}

<div use:ziehauswahl={{ an: auswahl.bearbeiten, art: "zeilen" }}>
  {#each eintraege as eintrag (eintragsschluessel(eintrag))}
    {#if eintrag.art === "sammlung"}{@render sammlungszeile(eintrag.sammlung)}
    {:else if auswahl.bearbeiten}
      {@const buch = eintrag.buch}
      <button type="button" class="zeile mehr" data-buch={buch.id} use:kontext={buchmenue(buch)} aria-pressed={auswahl.hat(buch.id)} onclick={() => auswahl.schalte(buch.id)}>{@render inhalt(buch)}</button>
    {:else}
      {@const buch = eintrag.buch}
      <a class="zeile mehr" data-buch={buch.id} use:kontext={buchmenue(buch)} href="/book/{buch.id}" aria-current={wahl.buch?.id === buch.id ? "true" : undefined} draggable="false" onclick={(e) => beimKlick(e, buch)}>{@render inhalt(buch)}</a>
    {/if}
  {/each}
</div>
{#if gross}<Grossbild buch={gross.buch} an={gross.an} />{/if}
