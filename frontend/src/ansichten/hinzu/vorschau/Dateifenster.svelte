<script lang="ts">
  // Eine Datei zuordnen (BF-80): Art, Kategorie, Sammlung und Band, Sprache, Doppel, beim Material das Buch dazu; jedes Feld
  // nennt seine Herkunft, darunter steht der Ablageort. "Speichern" ändert nur die Vorschau, ins Regal kommt erst etwas mit
  // "Übernehmen". Geschickt wird nur, was sich geändert hat, damit die übrigen Felder ihre Herkunft behalten.
  import { untrack } from "svelte";
  import { ablagetext, BESONDERES, doppelwerte, istBesonderes } from "../../../lib/annahme/vorschau";
  import type { Doppelwahl, Felderaenderung, Vorschauart, Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import { groesse, SPRACHEN } from "../../../lib/format";
  import { findeKategorie, farbeVon } from "../../../lib/katalog";
  import { arten } from "../../../lib/stand/arten.svelte";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Kategoriewahl from "../../../lib/teile/Kategoriewahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Herkunft from "./Herkunft.svelte";
  import Vorschaubild from "./Vorschaubild.svelte";
  import type { Vorschaustand } from "./vorschaustand.svelte";

  let { zeile, stand, onschliessen }: { zeile: Vorschauzeile; stand: Vorschaustand; onschliessen: () => void } = $props();

  type Hauptart = "buch" | "besonderes" | "material";
  const BUCHFORMAT = /\.(pdf|epub|mobi|txt|md)$/i;

  // Der Entwurf beginnt mit dem Stand beim Öffnen; ein Nachladen der Vorschau ändert ihn nicht
  const f = untrack(() => zeile.felder!);
  const startArt = f.art.wert as Vorschauart;
  const startZiel = f.ziel?.aufnahme ? `a${f.ziel.aufnahme}` : f.ziel?.buch_id ? `b${f.ziel.buch_id}` : "";
  let haupt = $state<Hauptart | "">(startArt === "material" ? "material" : istBesonderes(startArt) ? "besonderes" : startArt === "buch" ? "buch" : "");
  let unterart = $state<string>(istBesonderes(startArt) ? startArt : "dokument");
  let kategorien = $state<number[]>([...f.kategorien.wert]);
  let sammlung = $state(f.sammlung.wert ? String(f.sammlung.wert) : "");
  let band = $state(f.band.wert);
  let sprache = $state(f.sprache.wert);
  let doppel = $state<Doppelwahl>(f.doppel.wahl);
  let ziel = $state(startZiel);
  let kategorieOffen = $state(false);

  let buchformat = $derived(BUCHFORMAT.test(zeile.name));
  let artNeu = $derived<Vorschauart>(haupt === "material" ? "material" : haupt === "besonderes" ? (unterart as Vorschauart) : haupt);
  let kategorieliste = $derived(kategorien.map((id) => ({ id, fund: findeKategorie(bestand.katalog, id) })));
  let sammlungen = $derived<[string, string][]>([["", "keine"], ...bestand.sammlungen.map((s): [string, string] => [String(s.id), s.name])]);
  let sprachen = $derived<[string, string][]>([["", "unbekannt"], ...SPRACHEN, ...(sprache && !SPRACHEN.some(([k]) => k === sprache) ? [[sprache, sprache] as [string, string]] : [])]);
  /** Wozu Material gehören kann: die Werke dieser Vorschau, dazu ein Buch im Bestand, wenn es schon das Ziel ist */
  let ziele = $derived<[string, string][]>([
    ...stand.werke.filter((w) => w.id !== zeile.id).map((w): [string, string] => [`a${w.id}`, w.gelesen?.titel || w.name]),
    ...(f.ziel?.buch_id ? [[`b${f.ziel.buch_id}`, `${f.ziel.titel} (im Bestand)`] as [string, string]] : []),
  ]);
  let zielFehlt = $derived(haupt === "material" && !ziel);
  let lueckeBand = $derived(f.sammlung.herkunft === "luecke" && sammlung === String(f.sammlung.wert ?? "") ? band : "");

  const gleich = (a: readonly number[], b: readonly number[]) => a.length === b.length && a.every((x, n) => x === b[n]);

  function aenderungen(): Felderaenderung {
    const neu: Felderaenderung = {};
    if (artNeu !== startArt) neu.art = artNeu;
    if (haupt === "material" && ziel !== startZiel && ziel) neu.ziel = ziel.startsWith("a") ? { aufnahme: Number(ziel.slice(1)) } : { buch_id: Number(ziel.slice(1)) };
    if (startArt === "material" && haupt !== "material" && doppel !== "format") neu.ziel = null;
    if (!gleich(kategorien, f.kategorien.wert)) neu.kategorien = [...kategorien];
    if (sammlung !== (f.sammlung.wert ? String(f.sammlung.wert) : "")) neu.sammlung = sammlung ? Number(sammlung) : null;
    if (band.trim() !== f.band.wert) neu.band = band.trim();
    if (sprache !== f.sprache.wert && sprache) neu.sprache = sprache;
    if (doppel !== f.doppel.wahl) neu.doppel = doppel;
    return neu;
  }

  async function speichern() {
    const neu = aenderungen();
    if (!Object.keys(neu).length) return onschliessen();
    if (await stand.aendere([zeile.id], neu)) onschliessen();
  }

  function nimmKategorie(id: number | undefined) {
    kategorieOffen = false;
    if (id !== undefined && !kategorien.includes(id)) kategorien = [...kategorien, id];
  }
</script>

<Fenster titel="Datei zuordnen" breite="34rem" {onschliessen}>
  <div class="dateikopf"><span class="bild"><Vorschaubild {zeile} /></span><span class="vdatei"><b>{zeile.name}</b><small>{#if zeile.ordner}<Symbol name="folder" /> {zeile.ordner}, {/if}{groesse(zeile.groesse)}</small></span></div>

  <div class="feld">
    <span>Art<Herkunft herkunft={f.art.herkunft} mitText /></span>
    <div class="segment segmentvoll" role="group" aria-label="Art">
      <button type="button" aria-pressed={haupt === "buch"} disabled={!buchformat} title={buchformat ? undefined : "Kein lesbares Buchformat"} onclick={() => (haupt = "buch")}>Buch</button>
      <button type="button" aria-pressed={haupt === "besonderes"} disabled={!buchformat} title={buchformat ? undefined : "Kein lesbares Buchformat"} onclick={() => (haupt = "besonderes")}>Besonderes</button>
      <button type="button" aria-pressed={haupt === "material"} disabled={!ziele.length && haupt !== "material"} title={ziele.length ? undefined : "In dieser Vorschau gibt es kein Buch, zu dem sie gehören könnte"} onclick={() => (haupt = "material")}>Material</button>
    </div>
    {#if !haupt}<span class="leise">Noch offen, die App ordnet nach dem Übernehmen ein.</span>{/if}
  </div>
  {#if haupt === "besonderes"}
    <div class="feld"><span>Was für Besonderes</span><Auswahl name="Was für Besonderes" werte={BESONDERES.map((a): [string, string] => [a, arten.typName(a)])} wert={unterart} onwahl={(w) => (unterart = w)} /></div>
  {/if}
  {#if haupt === "material"}
    <div class="feld"><span>Gehört zu</span><Auswahl name="Gehört zu" werte={ziel ? ziele : [["", "bitte wählen"], ...ziele]} wert={ziel} onwahl={(w) => (ziel = w)} /></div>
  {:else}
    <div class="feld">
      <span>Kategorie<Herkunft herkunft={f.kategorien.herkunft} mitText /></span>
      <div class="reihe">
        {#each kategorieliste as k (k.id)}
          <Chip>
            {#if k.fund}<Katalogzeichen name={k.fund.kategorie.zeichen} farbe={farbeVon(k.fund.kategorie, k.fund.bereich)} groesse="klein" />{/if}{k.fund?.kategorie.name ?? `Kategorie ${k.id}`}
            <button type="button" class="heraus" aria-label="Kategorie herausnehmen" title="Herausnehmen" onclick={() => (kategorien = kategorien.filter((x) => x !== k.id))}><Symbol name="xmark" /></button>
          </Chip>
        {/each}
        {#if bestand.katalog?.hat_katalog}<Chip text="Kategorie" symbol="plus" gedrueckt={kategorieOffen} onclick={() => (kategorieOffen = !kategorieOffen)} />{/if}
      </div>
      {#if kategorieOffen && bestand.katalog}<div class="mulde kategorieauswahl"><Kategoriewahl bereiche={bestand.katalog.bereiche} ohne={kategorien} onwahl={(k) => nimmKategorie(k.id)} /></div>{/if}
    </div>
    <div class="zweifeld">
      <label class="feld"><span>Sammlung<Herkunft herkunft={f.sammlung.herkunft} mitText /></span><Auswahl name="Sammlung" werte={sammlungen} wert={sammlung} onwahl={(w) => (sammlung = w)} /></label>
      <label class="feld"><span>Band<Herkunft herkunft={f.band.herkunft} mitText /></span><input class="eingabe zahl" bind:value={band} inputmode="numeric" maxlength="20" disabled={!sammlung} /></label>
    </div>
    {#if lueckeBand}<p class="marke-text gut"><Symbol name="puzzle-piece" />In die Lücke Band {lueckeBand}</p>{/if}
    <div class="feld"><span>Sprache<Herkunft herkunft={f.sprache.herkunft} mitText /></span><Auswahl name="Sprache" werte={sprachen} wert={sprache} onwahl={(w) => (sprache = w)} /></div>
  {/if}
  <div class="feld">
    <span>Doppel<Herkunft herkunft={f.doppel.herkunft} mitText /></span>
    {#if f.doppel.art === "neu" && doppel === "neu"}
      <span class="marke-text gut"><Symbol name="plus" />Neu, im Bestand gibt es nichts Gleiches</span>
    {:else}
      <Auswahl name="Doppel" werte={doppelwerte({ ...f.doppel, wahl: doppel })} wert={doppel} gesperrt={f.doppel.art === "gleich"} onwahl={(w) => (doppel = w as Doppelwahl)} />
      {#if f.doppel.grund}<span class="leise">{f.doppel.grund}</span>{/if}
    {/if}
  </div>
  {#each f.hinweise as hinweis (hinweis.text)}<p class="marke-text warn"><Symbol name="triangle-exclamation" />{hinweis.text}<Herkunft herkunft={hinweis.herkunft} mitText /></p>{/each}
  {#if zeile.ablage}<dl class="angaben"><dt>Ablage</dt><dd class="pfad">{ablagetext(zeile.ablage)}</dd></dl>{/if}

  {#snippet fuss()}
    <span class="schiebt tasten2">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <Knopf text="Speichern" symbol="check" haupt gesperrt={zielFehlt || stand.arbeitet} titel={zielFehlt ? "Erst das Buch wählen, zu dem das Material gehört" : undefined} onclick={() => void speichern()} />
    </span>
  {/snippet}
</Fenster>

<style>
  .kategorieauswahl {
    padding: 0.5rem;
  }
  .heraus {
    display: inline-grid;
    place-items: center;
    color: var(--tinte-3);
    min-width: 1.25rem;
    align-self: stretch;
  }
  .heraus:hover {
    color: var(--tinte);
  }
</style>
