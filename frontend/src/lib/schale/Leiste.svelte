<script lang="ts">
  // Leiste links: Bestand, Lesen, Katalog, Regale, Sammlungen. Filter lassen sich kombinieren, "Alle" hebt sie auf.
  import { abmelden } from "../api/client";
  import { eingrenzen } from "../eingrenzen";
  import { offenesFeld } from "../flucht";
  import { zahl } from "../format";
  import { GRAUTON, bereichBeruehrt, bereichGewaehlt, farbeVon, schalteBereich, schalteKategorie, sichtbareBereiche } from "../katalog";
  import { route } from "../router.svelte";
  import { bestand } from "../stand/bestand.svelte";
  import { filter } from "../stand/filter.svelte";
  import { ich } from "../stand/ich.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { schale } from "../stand/schale.svelte";
  import Katalogzeichen from "../teile/Katalogzeichen.svelte";
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

  // Katalog (BF-69): ein Bereich filtert nach allen seinen Kategorien und klappt auf, solange eine davon gewählt ist
  let katalog = $derived(bestand.katalog);
  // Gefiltert wird nach allen Kategorien eines Bereichs, gezeigt werden die nicht verborgenen
  let bereiche = $derived(katalog?.hat_katalog ? katalog.bereiche.filter((b) => !b.verborgen) : []);
  let sichtbar = $derived(new Map(sichtbareBereiche(bereiche).map((b) => [b.schluessel, b.kategorien])));
  let gewaehlt = $derived(aufBibliothek ? filter.werte("category") : []);

  function zu() {
    schale.leisteOffen = false;
  }

  function waehleKategorien(werte: string[]) {
    filter.setzeWerte("category", werte);
    zu();
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
  <!-- Oben und der Fuß stehen; der Teil ab Katalog rollt in der restlichen Höhe, bleiben ihm zu wenige Zeilen, rollt alles -->
  <div class="rollen leiste-flaeche">
    <div class="leiste-oben">
      <Punkt text="Alle" symbol="layer-group" zahl={z.buecher_gesamt} gedrueckt={aufBibliothek && !filter.aktiv} onclick={() => { filter.leere(); zu(); }} />
      <!-- Nach der Art des Werks (BF-77): Bücher und alles, was kein Buch ist; die ISBN filtert unter "Mehr" -->
      {@render schalter("art", "buch", "Bücher", "book", z.buecher)}
      {@render schalter("art", "besonderes", "Besonderes", "shapes", z.besonderes)}
      <Punkt text="Autoren" symbol="users" zahl={z.autoren} href="/authors" hier={route.path.startsWith("/author")} onclick={zu} />
      <!-- Am Telefon hat die untere Leiste dafür Vollbild (BF-33) -->
      {#if ich.darf("hinzufuegen")}<span class="nur-telefon"><Punkt text="Hinzufügen" symbol="plus" href="/import" hier={route.path === "/import"} onclick={zu} /></span>{/if}

      <h2>Lesen</h2>
      {@render schalter("weiterlesen", "true", "Weiterlesen", "book-open", z.weiterlesen)}
      {@render schalter("is_favorite", "true", "Favoriten", "heart", z.favoriten)}
      {@render schalter("is_to_read", "true", "Lesesofa", "couch", z.leseliste)}
      {@render schalter("gelesen", "true", "Gelesen", "circle-check", z.gelesen)}
      {@render schalter("gelesen", "false", "Ungelesen", "circle-dot", z.ungelesen)}
      {@render schalter("hat_highlights", "true", "Markiertes", "highlighter", z.mit_highlights)}
    </div>

    <div class="leiste-unten">
      {#if katalog}
        <h2>Katalog</h2>
        {#each bereiche as b (b.schluessel)}
          {@const offen = bereichBeruehrt(b, gewaehlt)}
          {@const ganz = bereichGewaehlt(b, gewaehlt)}
          <button type="button" class="punkt bereichspunkt" aria-pressed={ganz} aria-expanded={offen} onclick={() => waehleKategorien(schalteBereich(b, gewaehlt))}>
            <Katalogzeichen name={b.zeichen} farbe={b.farbe} /><span class="name" title={b.name}>{b.name}</span><span class="zahl">{zahl(b.anzahl)}</span>
          </button>
          {#if offen}
            {#each sichtbar.get(b.schluessel) ?? [] as k (k.id)}
              <button type="button" class="punkt kategoriepunkt" aria-pressed={!ganz && gewaehlt.includes(String(k.id))} onclick={() => waehleKategorien(schalteKategorie(b, String(k.id), gewaehlt))}>
                <Katalogzeichen name={k.zeichen} farbe={farbeVon(k, b)} groesse="klein" /><span class="name" title={k.name}>{k.name}</span><span class="zahl">{zahl(k.anzahl)}</span>
              </button>
            {/each}
          {/if}
        {:else}
          {#if ich.darf("einstellungen")}<Punkt text="Katalog einrichten" symbol="sitemap" href="/settings/katalog" hier={route.path === "/settings/katalog"} onclick={zu} />{/if}
        {/each}
        {#if katalog.hat_katalog}
          <h2>Noch nicht eingeordnet</h2>
          <button type="button" class="punkt bereichspunkt" aria-pressed={an("ohne_kategorie", "true")} onclick={() => { filter.schalte("ohne_kategorie", "true"); zu(); }}>
            <Katalogzeichen name="inbox" farbe={GRAUTON} /><span class="name">Ohne Kategorie</span><span class="zahl">{zahl(katalog.ohne_kategorie)}</span>
          </button>
        {/if}
      {/if}

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
  </div>

  <div class="leiste-fuss">
    {#if ich.mitEinstellungen}<Punkt text="Einstellungen" symbol="gear" href="/settings" hier={route.path.startsWith("/settings")} onclick={zu} />{/if}
    <Leistenfuss />
  </div>
</nav>
