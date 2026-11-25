<script lang="ts">
  // Kompakte Liste: Spaltenköpfe sortieren
  import { formatName, groesse } from "../../lib/format";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { buecher, type Sortierung } from "../../lib/stand/buecher.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Buch } from "../../lib/typen";
  import Grossbild from "./Grossbild.svelte";
  import { beimKlick } from "./oeffnen";
  import { ziehauswahl } from "./ziehauswahl";

  let { liste, sortierbar = true }: { liste: Buch[]; sortierbar?: boolean } = $props();
  let gross = $state<{ buch: Buch; an: HTMLElement } | null>(null);

  const spalten: [string, Sortierung | null][] = [["Titel", "titel"], ["Autor", "autor"], ["Format", null], ["Größe", "groesse"], ["Bewertung", "bewertung"], ["Jahr", "jahr"]];
  const pfeil = $derived(buecher.richtung === "asc" ? "arrow-up-short-wide" : "arrow-down-wide-short");
</script>

{#snippet inhalt(buch: Buch)}
  <span class="bild" role="presentation" onpointerenter={(e) => e.pointerType === "mouse" && (gross = { buch, an: e.currentTarget })} onpointerleave={() => (gross = null)}>
    {#if auswahl.bearbeiten}<span class="haken"><Symbol name="check" /></span>{/if}<Umschlag {buch} />
  </span>
  <b>{buch.title}</b><span>{buch.author}</span><span>{formatName(buch.file_format)}</span><span class="zahl">{groesse(buch.file_size)}</span><span><Sterne wert={buch.rating} /></span><span class="zahl">{buch.year ?? ""}</span>
{/snippet}

<div use:ziehauswahl={{ an: auswahl.bearbeiten, art: "zeilen" }}>
  <div class="zeile kopfzeile">
    <span></span>
    {#each spalten as [text, nach] (text)}
      {#if nach && sortierbar}
        <button type="button" onclick={() => buecher.sortiere(nach)} title="Nach {text} sortieren">{text}{#if buecher.sortierung === nach}{" "}<Symbol name={pfeil} />{/if}</button>
      {:else}<span>{text}</span>{/if}
    {/each}
  </div>
  {#each liste as buch (buch.id)}
    {#if auswahl.bearbeiten}
      <button type="button" class="zeile" data-buch={buch.id} aria-pressed={auswahl.hat(buch.id)} onclick={() => auswahl.schalte(buch.id)}>{@render inhalt(buch)}</button>
    {:else}
      <a class="zeile" data-buch={buch.id} href="/book/{buch.id}" aria-current={wahl.buch?.id === buch.id ? "true" : undefined} draggable="false" onclick={(e) => beimKlick(e, buch)}>{@render inhalt(buch)}</a>
    {/if}
  {/each}
</div>
{#if gross}<Grossbild buch={gross.buch} an={gross.an} />{/if}
