<script lang="ts">
  // Bild einer Datei in der Vorschau: der Umschlag, den das Lesen fand, sonst das gestaltete Blatt (BF-59), ohne Angaben das
  // Zeichen der Datei
  import { aufnahmeUmschlag } from "../../../lib/api/annahme";
  import { dateizeichen, istBesonderes } from "../../../lib/annahme/vorschau";
  import type { Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import Deckblatt from "../../../lib/teile/Deckblatt.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { zeile }: { zeile: Pick<Vorschauzeile, "id" | "name" | "umschlag" | "gelesen" | "felder" | "rolle"> } = $props();
  let kaputt = $state(false);
  let art = $derived(zeile.felder?.art.wert ?? "");
  let mitBild = $derived(zeile.umschlag && !zeile.gelesen?.umschlag_schlicht && !kaputt);
  let blatt = $derived(zeile.gelesen && zeile.rolle !== "material"
    ? { id: zeile.id, title: zeile.gelesen.titel || zeile.name.replace(/\.[^.]+$/, ""), author: zeile.gelesen.autor, year: zeile.gelesen.jahr, typ: istBesonderes(art) ? art : "", gattung: zeile.felder?.gattung ?? "" }
    : null);
</script>

{#if mitBild}
  <span class="umschlag"><img src={aufnahmeUmschlag(zeile.id)} alt="" loading="lazy" decoding="async" draggable="false" onerror={() => (kaputt = true)} /></span>
{:else if blatt}
  <span class="umschlag"><Deckblatt buch={blatt} /></span>
{:else}
  <span class="dateizeichen"><Symbol name={dateizeichen(zeile.name)} /></span>
{/if}
