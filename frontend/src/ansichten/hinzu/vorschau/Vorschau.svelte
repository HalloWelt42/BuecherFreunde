<script lang="ts">
  // Die Vorschau beim Hochladen (BF-80) als eigene Ansicht: je Datei, was beim Übernehmen geschieht; alles lässt sich vorher
  // ändern, einzeln oder für alle angehakten. Werkzeug, Auswahl und Fuß stehen, nur die Liste rollt. Erst "Übernehmen"
  // stellt etwas ins Regal; "Verwerfen" fragt vorher mit allen Dateien und ihrer Wirkung.
  import { FILTER, fusstext, type Vorschaufilter } from "../../../lib/annahme/vorschau";
  import type { Felderaenderung, Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import { arten } from "../../../lib/stand/arten.svelte";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import { navigate } from "../../../lib/router.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Zustand from "../../../lib/teile/Zustand.svelte";
  import Dateifenster from "./Dateifenster.svelte";
  import Feldwahl, { FELDER, type Feld } from "./Feldwahl.svelte";
  import Legende from "./Legende.svelte";
  import Nichtzeile from "./Nichtzeile.svelte";
  import Vorschaubild from "./Vorschaubild.svelte";
  import Dateizeile from "./Vorschauzeile.svelte";
  import { Vorschaustand } from "./vorschaustand.svelte";

  let { params }: { params: Record<string, string> } = $props();

  let stand = $derived(new Vorschaustand(params.id));
  let v = $derived(stand.vorschau);

  $effect(() => {
    void bestand.laden();
    void arten.laden();
  });

  // Laden, und neu laden, sobald sich am Server etwas an dieser Vorschau tut (Ereignisstrom der Annahme)
  $effect(() => {
    void stand.kennung;
    void stand.laden();
  });
  // Solange die KI prüft oder etwas läuft, zusätzlich nachsehen
  $effect(() => {
    void stand.vorschau;
    return stand.nachsehen();
  });

  // Ein Feld für alle angehakten: am Rechner je Feld ein Knopf, am Telefon "Ändern" mit der Wahl des Felds davor
  let feld = $state<Feld | "wahl" | "">("");
  let anker = $state<HTMLElement | null>(null);
  const knoepfe: Record<Feld | "telefon", HTMLElement | null> = $state({ art: null, kategorie: null, sammlung: null, sprache: null, doppel: null, telefon: null });
  let einzeln = $state<Vorschauzeile | null>(null);
  let materialFuer = $state<{ zeile: Vorschauzeile; anker: HTMLElement } | null>(null);

  function oeffne(f: Feld | "wahl", knopf: HTMLElement | null | undefined) {
    if (feld === f) return void (feld = "");
    feld = f;
    anker = knopf ?? null;
  }

  async function setze(felder: Felderaenderung) {
    const ids = stand.auswahl.map((z) => z.id);
    feld = "";
    await stand.aendere(ids, felder);
  }

  async function alsMaterial(werk: Vorschauzeile) {
    const z = materialFuer?.zeile;
    materialFuer = null;
    if (z) await stand.aendere([z.id], { art: "material", ziel: { aufnahme: werk.id } });
  }

  async function verwerfen() {
    if (await stand.verwirf()) navigate("/import");
  }

  let zahl = $derived(stand.auswahl.length);
  let alleAn = $derived(stand.waehlbar.length > 0 && stand.waehlbar.every((z) => stand.gewaehlt.includes(z.id)));
  let filterwerte = $derived(FILTER.map(([f, t]): [string, string] => [f, `${t} (${stand.zahlen[f]})`]));
  let mitKatalog = $derived(!!bestand.katalog?.hat_katalog);
</script>

<div class="werkzeug">
  <Knopf text="Hinzufügen" symbol="arrow-left" klein href="/import" />
  <h1>Vorschau</h1>
  {#if v}<span class="leise zahl">{stand.kopf}</span>{/if}
  {#if v && stand.zeilen.length}
    <span class="reihe schiebt vfilter">{#each FILTER as [f, text] (f)}<Chip {text} zahl={stand.zahlen[f]} gedrueckt={stand.filter === f} onclick={() => (stand.filter = f)} />{/each}</span>
    <span class="vfilterwahl"><Auswahl name="Zeigen" werte={filterwerte} wert={stand.filter} onwahl={(w) => (stand.filter = w as Vorschaufilter)} /></span>
  {/if}
</div>

{#if stand.fehler && !v}
  <div class="inhalt rollen"><Zustand art="fehler" text={stand.fehler} onerneut={() => void stand.laden()}><Knopf text="Hinzufügen" symbol="arrow-left" klein href="/import" /></Zustand></div>
{:else if !v}
  <div class="inhalt rollen"><Zustand art="laedt" text="Vorschau wird geladen" /></div>
{:else}
  <div class="inhalt vflaeche">
    {#if !stand.offen}
      <Zustand text={v.stand === "uebernommen" ? `Übernommen.${v.hinweis ? ` ${v.hinweis}.` : ""}` : "Verworfen. Ins Regal kam nichts."}><Knopf text="Zu den Aufnahmen" symbol="list-check" klein href="/import" /></Zustand>
    {:else}
      <div class="vauswahl">
        <Haekchen text="Alle" an={alleAn} gesperrt={!stand.waehlbar.length} onwahl={(an) => stand.alle(an)} />
        <b class="zahl">{zahl ? `${zahl} gewählt` : "keine gewählt"}</b>
        <div class="vaendern">
          {#each FELDER as [f, text, symbol] (f)}
            <Knopf {text} {symbol} klein gesperrt={!zahl || stand.arbeitet || (f === "kategorie" && !mitKatalog)} titel={f === "kategorie" && !mitKatalog ? "Es gibt noch keinen Katalog" : `${text} für alle angehakten`} aufgeklappt={feld === f} bind:element={knoepfe[f]} onclick={() => oeffne(f, knoepfe[f])} />
          {/each}
          <Knopf text="Aufheben" symbol="xmark" klein frei gesperrt={!zahl} titel="Auswahl aufheben" onclick={() => stand.aufheben()} />
        </div>
        <span class="vaendern-tel">
          <Knopf text="Ändern" symbol="pen" klein gesperrt={!zahl || stand.arbeitet} titel="Art, Kategorie, Sammlung, Sprache oder Doppel für alle angehakten" aufgeklappt={feld !== ""} bind:element={knoepfe.telefon} onclick={() => oeffne("wahl", knoepfe.telefon)} />
          <Knopf text="Auswahl aufheben" symbol="xmark" nur klein frei gesperrt={!zahl} onclick={() => stand.aufheben()} />
        </span>
      </div>
    {/if}
    <Legende lage="oben" />
    <div class="vzeile kopfzeile" aria-hidden="true"><span></span><span></span><span>Datei</span><span class="felder"><span>Art</span><span>Kategorie</span><span>Sammlung</span><span>Sprache</span><span>Doppel</span><span>Material</span></span><span></span></div>
    <div class="vliste rollen">
      {#each stand.unterwegs as h (h.schluessel)}
        <div class="vzeile">
          <span></span>
          <span class="bild"><Vorschaubild zeile={{ id: 0, name: h.name, umschlag: false, gelesen: null, felder: null, rolle: "buch" }} /></span>
          <span class="vdatei"><b>{h.name}</b><small>{Math.round(h.anteil * 100)} %</small></span>
          <span class="felder"><span class="vlaeuft marke-text {h.lage === 'fehler' || h.lage === 'ohne_verbindung' ? 'warn' : 'info'}"><Symbol name={h.lage === "fehler" ? "triangle-exclamation" : "circle-notch"} dreht={h.lage !== "fehler"} />{h.text}</span></span>
          <span></span>
        </div>
      {/each}
      {#each stand.liste as zeile (zeile.id)}<Dateizeile {zeile} {stand} onaendern={(z) => (einzeln = z)} />{/each}
      {#if !stand.liste.length && !stand.unterwegs.length}<p class="leise">{stand.zeilen.length ? "Hier steht gerade nichts." : "Noch keine Datei in dieser Vorschau."}</p>{/if}
      {#if stand.rest.length}
        <section class="vnicht">
          <h3><Symbol name="circle-minus" />Nicht übernommen <span class="leise zahl">{stand.rest.length}</span></h3>
          {#each stand.rest as zeile (zeile.id)}<Nichtzeile {zeile} {stand} offen={materialFuer?.zeile.id === zeile.id} onmaterial={(z, a) => (materialFuer = materialFuer?.zeile.id === z.id ? null : { zeile: z, anker: a })} />{/each}
        </section>
      {/if}
      <Legende lage="unten" />
    </div>
    {#if stand.offen}
      <div class="vfuss">
        <span class="leise zahl">{fusstext(v.zaehler)}</span>
        {#if v.zaehler.laeuft}<span class="marke-text info"><Symbol name="circle-notch" dreht />{v.zaehler.laeuft} {v.zaehler.laeuft === 1 ? "läuft" : "laufen"} noch</span>{/if}
        {#if v.zaehler.ki}<span class="marke-text info"><Symbol name="circle-notch" dreht />KI prüft noch {v.zaehler.ki}</span>{/if}
        <span class="tasten2 schiebt">
          <Knopf text="Verwerfen" symbol="trash" gesperrt={stand.arbeitet} onclick={() => void verwerfen()} />
          <Knopf text="Übernehmen ({v.zaehler.uebernehmen})" symbol="check" haupt laeuft={stand.uebernimmt} gesperrt={!v.zaehler.uebernehmen || stand.arbeitet} titel={v.zaehler.uebernehmen ? undefined : "Es wartet nichts, was ins Regal kommen könnte"} onclick={() => void stand.uebernimm()} />
        </span>
      </div>
    {/if}
  </div>
{/if}

{#if feld && anker}
  <Menue {anker} name={feld === "wahl" ? "Was ändern" : `${FELDER.find(([f]) => f === feld)?.[1]} für ${zahl}`} breite="19rem" onschliessen={() => (feld = "")}>
    {#if feld === "wahl"}
      <div class="feldkopf"><b>Ändern für {zahl}</b><span class="schiebt"><Knopf text="Schließen" symbol="xmark" nur klein frei onclick={() => (feld = "")} /></span></div>
      <div class="feldliste">
        {#each FELDER as [f, text, symbol] (f)}<button type="button" class="punkt" disabled={f === "kategorie" && !mitKatalog} onclick={() => (feld = f)}><Symbol name={symbol} /><span class="name">{text}</span></button>{/each}
      </div>
    {:else}
      <Feldwahl {feld} zeilen={stand.auswahl} onwahl={(f) => void setze(f)} onschliessen={() => (feld = "")} />
    {/if}
  </Menue>
{/if}

{#if materialFuer}
  <Menue anker={materialFuer.anker} name="Als Material zu" breite="19rem" onschliessen={() => (materialFuer = null)}>
    <div class="feldkopf"><b>Als Material zu</b><span class="schiebt"><Knopf text="Schließen" symbol="xmark" nur klein frei onclick={() => (materialFuer = null)} /></span></div>
    <div class="feldliste">
      {#each stand.werke as w (w.id)}<button type="button" class="punkt" onclick={() => void alsMaterial(w)}><Symbol name="book" /><span class="name">{w.gelesen?.titel || w.name}</span></button>{/each}
    </div>
  </Menue>
{/if}

{#if einzeln}
  <Dateifenster zeile={einzeln} {stand} onschliessen={() => (einzeln = null)} />
{/if}
