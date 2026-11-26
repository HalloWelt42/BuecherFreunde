<script lang="ts">
  // Leiste links: Bestand, Lesen, Regale, Sammlungen. Filter lassen sich kombinieren, "Alle" hebt sie auf.
  import { abmelden } from "../api/client";
  import { eingrenzen } from "../eingrenzen";
  import { offenesFeld } from "../flucht";
  import { zahl } from "../format";
  import { route } from "../router.svelte";
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

  // Bei vielen Regalen oder Sammlungen eine Suche und höchstens so viele Treffer; bei wenigen bleibt alles, wie es ist
  const HOECHSTENS = 20;
  let regalwort = $state("");
  let sammlungswort = $state("");
  let regale = $derived(eingrenzen(bestand.leistenRegale, (r) => r.name, regalwort, (r) => an("category", String(r.id)), HOECHSTENS));
  let sammlungen = $derived(eingrenzen(bestand.sammlungen, (s) => s.name, sammlungswort, (s) => an("sammlung", String(s.id)), HOECHSTENS));

  function zu() {
    schale.leisteOffen = false;
  }

  // Über dem Inhalt aufgeklappt (schmal, Telefon): Esc und ein Druck daneben klappen sie zu; ihre Schalter gehören dazu
  let leiste: HTMLElement | undefined = $state();
  $effect(() => {
    if (schale.leisteOffen) return offenesFeld(() => [leiste, ...document.querySelectorAll("[data-leistenschalter], .kopf .leisteknopf")], zu);
  });

  async function ab() {
    zu();
    await abmelden();
  }
</script>

{#snippet schalter(schluessel: string, wert: string, text: string, symbol: string, n: number)}
  <Punkt {text} {symbol} zahl={n} gedrueckt={an(schluessel, wert)} onclick={() => { filter.schalte(schluessel, wert); zu(); }} />
{/snippet}

<nav class="leiste glas milch" aria-label="Bereiche" bind:this={leiste}>
  <div class="rollen">
    <Punkt text="Alle" symbol="layer-group" zahl={z.buecher_gesamt} gedrueckt={aufBibliothek && !filter.aktiv} onclick={() => { filter.leere(); zu(); }} />
    {@render schalter("hat_isbn", "true", "Bücher", "book", z.buecher_mit_isbn)}
    {@render schalter("hat_isbn", "false", "Dokumente", "file-lines", z.dokumente)}
    <Punkt text="Autoren" symbol="users" zahl={z.autoren} href="/authors" hier={route.path.startsWith("/author")} onclick={zu} />
    <!-- Am Telefon hat die untere Leiste dafür Vollbild (BF-33) -->
    <span class="nur-telefon"><Punkt text="Hinzufügen" symbol="plus" href="/import" hier={route.path === "/import"} onclick={zu} /></span>

    <h2>Lesen</h2>
    {@render schalter("weiterlesen", "true", "Weiterlesen", "book-open", z.weiterlesen)}
    {@render schalter("is_favorite", "true", "Favoriten", "heart", z.favoriten)}
    {@render schalter("is_to_read", "true", "Lesesofa", "couch", z.leseliste)}
    {@render schalter("gelesen", "true", "Gelesen", "circle-check", z.gelesen)}
    {@render schalter("gelesen", "false", "Ungelesen", "circle-dot", z.ungelesen)}
    {@render schalter("hat_highlights", "true", "Markiertes", "highlighter", z.mit_highlights)}

    {#if bestand.leistenRegale.length}
      <h2>Regale</h2>
      {#if regale.mitSuche}<input class="eingabe leistensuche" type="search" placeholder="Regal suchen" aria-label="Regal suchen" bind:value={regalwort} />{/if}
      {#each regale.gezeigt as regal (regal.id)}
        <Punkt text={regal.name} symbol={regal.icon || "folder"} symbolfarbe={regal.color} zahl={regal.buch_anzahl} gedrueckt={an("category", String(regal.id))} onclick={() => { filter.schalte("category", String(regal.id)); zu(); }} />
      {:else}<p class="leise leistenhinweis">Kein Regal heißt so.</p>{/each}
      {#if regale.weitere}<p class="leise leistenhinweis">Noch {zahl(regale.weitere)} weitere, Suche verfeinern.</p>{/if}
    {/if}

    {#if bestand.sammlungen.length}
      <h2>Sammlungen</h2>
      {#if sammlungen.mitSuche}<input class="eingabe leistensuche" type="search" placeholder="Sammlung suchen" aria-label="Sammlung suchen" bind:value={sammlungswort} />{/if}
      {#each sammlungen.gezeigt as s (s.id)}
        <button type="button" class="punkt" aria-pressed={an("sammlung", String(s.id))} onclick={() => { filter.schalte("sammlung", String(s.id)); zu(); }}>
          <span class="farbe" style:background={s.color}></span><span class="name">{s.name}</span><span class="zahl">{zahl(s.buch_anzahl)}</span>
        </button>
      {:else}<p class="leise leistenhinweis">Keine Sammlung heißt so.</p>{/each}
      {#if sammlungen.weitere}<p class="leise leistenhinweis">Noch {zahl(sammlungen.weitere)} weitere, Suche verfeinern.</p>{/if}
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
