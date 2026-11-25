<script lang="ts">
  // Leiste links: Bestand, Lesen, Regale, Sammlungen. Filter lassen sich kombinieren, "Alle" hebt sie auf.
  import { abmelden } from "../api/client";
  import { zahl } from "../format";
  import { route } from "../router.svelte.js";
  import { bestand } from "../stand/bestand.svelte";
  import { filter } from "../stand/filter.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { schale } from "../stand/schale.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Leistenfuss from "./Leistenfuss.svelte";
  import Punkt from "./Punkt.svelte";

  const z = $derived(bestand.zahlen);
  const aufBibliothek = $derived(route.path === "/");
  const an = (k: string, w: string) => aufBibliothek && filter.hat(k, w);

  function zu() {
    schale.leisteOffen = false;
  }

  async function ab() {
    zu();
    await abmelden();
  }
</script>

{#snippet schalter(schluessel: string, wert: string, text: string, symbol: string, n: number)}
  <Punkt {text} {symbol} zahl={n} gedrueckt={an(schluessel, wert)} onclick={() => { filter.schalte(schluessel, wert); zu(); }} />
{/snippet}

<nav class="leiste glas milch" aria-label="Bereiche">
  <div class="rollen">
    <Punkt text="Alle" symbol="layer-group" zahl={z.buecher_gesamt} gedrueckt={aufBibliothek && !filter.aktiv} onclick={() => { filter.leere(); zu(); }} />
    {@render schalter("hat_isbn", "true", "Bücher", "book", z.buecher_mit_isbn)}
    {@render schalter("hat_isbn", "false", "Dokumente", "file-lines", z.dokumente)}
    <Punkt text="Autoren" symbol="users" zahl={z.autoren} href="/authors" hier={route.path.startsWith("/author")} onclick={zu} />

    <h2>Lesen</h2>
    {@render schalter("weiterlesen", "true", "Weiterlesen", "book-open", z.weiterlesen)}
    {@render schalter("is_favorite", "true", "Favoriten", "heart", z.favoriten)}
    {@render schalter("is_to_read", "true", "Lesesofa", "couch", z.leseliste)}
    {@render schalter("gelesen", "true", "Gelesen", "circle-check", z.gelesen)}
    {@render schalter("gelesen", "false", "Ungelesen", "circle-dot", z.ungelesen)}
    {@render schalter("hat_highlights", "true", "Markiertes", "highlighter", z.mit_highlights)}

    {#if bestand.leistenRegale.length}
      <h2>Regale</h2>
      {#each bestand.leistenRegale as regal (regal.id)}
        <Punkt text={regal.name} symbol={regal.icon || "folder"} symbolfarbe={regal.color} zahl={regal.buch_anzahl} gedrueckt={an("category", String(regal.id))} onclick={() => { filter.schalte("category", String(regal.id)); zu(); }} />
      {/each}
    {/if}

    {#if bestand.sammlungen.length}
      <h2>Sammlungen</h2>
      {#each bestand.sammlungen as s (s.id)}
        <button type="button" class="punkt" aria-pressed={an("sammlung", String(s.id))} onclick={() => { filter.schalte("sammlung", String(s.id)); zu(); }}>
          <span class="farbe" style:background={s.color}></span><span class="name">{s.name}</span><span class="zahl">{zahl(s.buch_anzahl)}</span>
        </button>
      {/each}
    {/if}

    <!-- Was der Kopf in schmalen Fenstern nicht mehr zeigt -->
    <span class="nur-kompakt">
      <h2>Weiteres</h2>
      <Punkt text="Schnellnotiz" symbol="note-sticky" zahl={notizblock.woerter} gedrueckt={schale.notizOffen} onclick={() => { schale.notizOffen = !schale.notizOffen; zu(); }} />
      <Punkt text="Danke sagen" symbol="heart" href="/danke" hier={route.path === "/danke"} onclick={zu} />
      <button type="button" class="punkt" onclick={ab}><Symbol name="right-from-bracket" /><span class="name">Abmelden</span></button>
    </span>
  </div>

  <div class="leiste-fuss">
    <Punkt text="Einstellungen" symbol="gear" href="/settings" hier={route.path.startsWith("/settings")} onclick={zu} />
    <Leistenfuss />
  </div>
</nav>
