<script lang="ts" module>
  /** Was sich für alle angehakten Dateien auf einmal setzen lässt */
  export type Feld = "art" | "kategorie" | "sammlung" | "sprache" | "doppel";
  export const FELDER: [Feld, string, string][] = [["art", "Art", "shapes"], ["kategorie", "Kategorie", "sitemap"], ["sammlung", "Sammlung", "layer-group"], ["sprache", "Sprache", "language"], ["doppel", "Doppel", "clone"]];
</script>

<script lang="ts">
  // Ein Feld für alle angehakten Dateien setzen (BF-80): Art, Kategorie, Sammlung, Sprache oder Doppel. Was für die Auswahl
  // nicht geht, ist gesperrt und sagt warum; der Server prüft dasselbe.
  import { ARTWAHL, doppelFuerAlle } from "../../../lib/annahme/vorschau";
  import type { Doppelwahl, Felderaenderung, Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import { SPRACHEN } from "../../../lib/format";
  import { arten } from "../../../lib/stand/arten.svelte";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import Flagge from "../../../lib/teile/Flagge.svelte";
  import Kategoriewahl from "../../../lib/teile/Kategoriewahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { feld, zeilen, onwahl, onschliessen }: { feld: Feld; zeilen: readonly Vorschauzeile[]; onwahl: (felder: Felderaenderung) => void; onschliessen: () => void } = $props();

  const BUCHFORMAT = /\.(pdf|epub|mobi|txt|md)$/i;
  let titel = $derived(`${FELDER.find(([f]) => f === feld)?.[1] ?? ""} für ${zeilen.length}`);
  let nurBuchformate = $derived(zeilen.every((z) => BUCHFORMAT.test(z.name)));
  let doppel = $derived(doppelFuerAlle(zeilen));
  let suche = $state("");
  let sammlungen = $derived(bestand.sammlungen.filter((s) => !suche.trim() || s.name.toLocaleLowerCase("de").includes(suche.trim().toLocaleLowerCase("de"))));

  const DOPPEL: [Doppelwahl, string, string, string][] = [
    ["weglassen", "Weglassen", "eye-slash", "Die Datei bleibt im Eingang"],
    ["eigenes", "Als eigenes Buch", "book", "Dieselbe Datei gibt es nur einmal"],
    ["format", "Weiteres Format", "clone", "Nur für Dateien, zu denen es das Buch schon gibt"],
    ["neu", "Neu", "plus", "Nur für Dateien ohne Doppel"],
  ];
</script>

<div class="feldkopf"><b>{titel}</b><span class="schiebt"><Knopf text="Schließen" symbol="xmark" nur klein frei onclick={onschliessen} /></span></div>
{#if feld === "art"}
  {#if !nurBuchformate}<p class="leise">Nicht jede angehakte Datei ist ein lesbares Buchformat.</p>{/if}
  <div class="feldliste">
    {#each ARTWAHL as a, n (a)}
      {#if n === 1}<h2 class="gruppe">Besonderes</h2>{/if}
      <button type="button" class="punkt" disabled={!nurBuchformate} onclick={() => onwahl({ art: a })}><Symbol name={a === "buch" ? "book" : "shapes"} /><span class="name">{a === "buch" ? "Buch" : arten.typName(a)}</span></button>
    {/each}
  </div>
{:else if feld === "kategorie"}
  {#if bestand.katalog?.hat_katalog}
    <Kategoriewahl bereiche={bestand.katalog.bereiche} onwahl={(k) => k.id !== undefined && onwahl({ kategorien: [k.id] })} />
  {:else}
    <p class="leise">Es gibt noch keinen Katalog.</p>
  {/if}
{:else if feld === "sammlung"}
  {#if bestand.sammlungen.length > 8}<form class="feld" onsubmit={(e) => { e.preventDefault(); if (sammlungen[0]) onwahl({ sammlung: sammlungen[0].id }); }}><input class="eingabe" type="search" placeholder="Sammlung suchen" aria-label="Sammlung suchen" bind:value={suche} data-fokus /></form>{/if}
  <div class="feldliste">
    <button type="button" class="punkt" onclick={() => onwahl({ sammlung: null })}><Symbol name="xmark" /><span class="name">Keine Sammlung</span></button>
    {#each sammlungen as s (s.id)}<button type="button" class="punkt" onclick={() => onwahl({ sammlung: s.id })}><span class="farbe" style:background={s.color || "var(--tinte-3)"}></span><span class="name">{s.name}</span></button>{/each}
  </div>
{:else if feld === "sprache"}
  <div class="feldliste">
    {#each SPRACHEN as [kuerzel, name] (kuerzel)}<button type="button" class="punkt" onclick={() => onwahl({ sprache: kuerzel })}><Flagge sprache={kuerzel} groesse="1.125rem" /><span class="name">{name}</span></button>{/each}
  </div>
{:else}
  <div class="feldliste">
    {#each DOPPEL as [wahl, text, symbol, warum] (wahl)}
      <button type="button" class="punkt" disabled={!doppel[wahl]} title={doppel[wahl] ? undefined : warum} onclick={() => onwahl({ doppel: wahl })}><Symbol name={symbol} /><span class="name">{text}</span></button>
    {/each}
  </div>
{/if}
