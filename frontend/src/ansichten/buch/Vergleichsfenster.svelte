<script lang="ts">
  // Angaben vergleichen im Fenster (BF-111, BF-112): die Quelle wählbar (Alle, Verzeichnisse, Lexikon, Datei), mit einer ISBN aus
  // dem Buch nur über sie. Vorgewählt sind echte Abweichungen; ist das gefundene Buch ein anderes, warnt die Zeile über der Tabelle
  // mit fremdem Titel und Fundort, und nichts ist vorgewählt (Abnahme 4). Beim Bearbeiten ist "Bisher" das Formular.
  import { untrack } from "svelte";
  import { coverUrl, type Einstufung, type Isbnkandidat } from "../../lib/api/books";
  import { sucheMetadaten } from "../../lib/api/metadata";
  import { anzahl, formatName } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { quellen } from "../../lib/stand/quellen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Vergleichstabelle, { type Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";
  import { ALLE, DATEI, fundart, vergleiche, type Vorschlag } from "./angaben";
  import { fremdHerkunft } from "./isbn";
  import Rohdaten from "./Rohdaten.svelte";
  import type { Angabenwerkzeuge } from "./werkzeuge.svelte";

  /** isbn: null die gespeicherte, leer ohne ISBN (über Titel und Autor), sonst nur diese */
  let { werkzeuge: w, quelle: start, isbn = null, kandidat = null }: { werkzeuge: Angabenwerkzeuge; quelle: string; isbn?: string | null; kandidat?: Isbnkandidat | null } = $props();

  // svelte-ignore state_referenced_locally
  let quelle = $state(start);
  let sucht = $state(false);
  let speichert = $state(false);
  let hinweis = $state("");
  let nebenbei = $state<string[]>([]);
  let vorschlag = $state<Vorschlag | null>(null);
  let abgleich = $state<Einstufung | null>(null);
  let bisherTitel = $state("");
  let zeilen = $state<Vergleichszeile[]>([]);
  let listen = $state<string[]>([]);

  let werte = $derived<[string, string][]>([...(quellen.buecher.length > 1 ? [[ALLE, "Alle"] as [string, string]] : []), ...quellen.buecher.map((q) => [q.kennung, q.name] as [string, string]), [DATEI, "Datei"]]);
  let namen = $derived({ ...quellen.namen, [DATEI]: "Datei" });
  let gewaehlt = $derived(zeilen.filter((z) => z.gewaehlt && !z.gleich).map((z) => z.schluessel));
  let zahlGewaehlt = $derived(gewaehlt.length + listen.length);
  let anders = $derived(abgleich?.stufe === "fremd");

  $effect(() => void quellen.bereit());
  $effect(() => {
    const q = quelle;
    untrack(() => void suche(q));
  });

  async function suche(q: string) {
    sucht = true;
    hinweis = "";
    nebenbei = [];
    vorschlag = null;
    abgleich = null;
    zeilen = [];
    listen = [];
    try {
      const frage = w.ziel.frage();
      const a = await sucheMetadaten(w.buch.id, q, { ...(isbn !== null && q !== DATEI ? { isbn } : {}), ...(frage ?? {}) });
      nebenbei = a.hinweise ?? [];
      if (nebenbei.length) melde.warn(`${nebenbei.join(". ")}. Gesucht wurde mit den übrigen Quellen.`);
      if (!a.angereichert || !a.vorschlag || !a.aktuell) {
        hinweis = a.grund ?? "Nichts gefunden.";
        return;
      }
      const bisher = w.ziel.aktuell() ?? a.aktuell;
      bisherTitel = String(bisher.titel ?? "");
      vorschlag = a.vorschlag;
      abgleich = a.abgleich ?? null;
      const neu = vergleiche(a.vorschlag, bisher, w.ziel.bild() ?? coverUrl(w.buch.id), q === ALLE ? namen : {});
      zeilen = abgleich?.stufe === "fremd" ? neu.map((z) => ({ ...z, gewaehlt: false })) : neu;
    } catch (e) {
      hinweis = e instanceof Error ? e.message : String(e);
    } finally {
      sucht = false;
    }
  }

  async function uebernimm() {
    if (!vorschlag) return;
    speichert = true;
    try {
      await w.ziel.angaben({ vorschlag, quelle, gewaehlt: new Set(gewaehlt), listen: new Set(listen) });
      w.schliesse();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      speichert = false;
    }
  }

  function waehle(schluessel: string, an: boolean) {
    zeilen = zeilen.map((z) => (z.schluessel === schluessel ? { ...z, gewaehlt: an } : z));
  }

  let gefunden = $derived(vorschlag ? fundart(vorschlag) : null);
</script>

<Fenster titel="Angaben vergleichen" breite="48rem" onschliessen={() => w.schliesse()}>
  <div class="vergleichskopf">
    <Auswahl name="Quelle" {werte} wert={quelle} gesperrt={sucht} onwahl={(q) => (quelle = q)} />
    {#if isbn && w.suche}<Knopf text={isbn} symbol="arrow-left" klein frei klasse="zahl" titel="Zurück zu den Kandidaten, andere ISBN wählen" onclick={() => w.zurueck()} />{/if}
    {#if sucht}<span class="leise"><Symbol name="circle-notch" dreht /> wird gesucht</span>{/if}
  </div>
  {#if hinweis}<p class="marke-text warn" role="status"><Symbol name="triangle-exclamation" /><span>{hinweis}</span></p>{/if}
  {#if vorschlag}
    {#if anders}
      <p class="marke-text warn" role="status"><Symbol name="triangle-exclamation" /><span>Anderes Buch: <b>{vorschlag.titel || "ohne Titel"}</b> statt {bisherTitel || "dem Titel des Buchs"}.{fremdHerkunft(kandidat, w.buch)} Nichts vorgewählt.</span></p>
    {:else if abgleich?.stufe === "passt"}
      <p class="marke-text gut"><Symbol name="circle-check" />Über die ISBN gefunden, Titel und Autor passen</p>
    {:else if abgleich?.stufe === "aehnlich"}
      <p class="marke-text info"><Symbol name="circle-half-stroke" /><span>Über die ISBN gefunden, Titel und Autor ähnlich{abgleich.warum ? `: ${abgleich.warum}` : ""}</span></p>
    {:else if quelle === DATEI}
      <p class="marke-text info"><Symbol name="file-import" />Aus den Angaben in der Datei ({formatName(w.buch.file_format)})</p>
    {:else if gefunden}
      <p class="marke-text {gefunden.ton}"><Symbol name={gefunden.ton === "gut" ? "circle-check" : "circle-question"} />{gefunden.text}</p>
    {/if}
    {#each nebenbei as grund (grund)}<p class="leise klein"><Symbol name="circle-info" /> {grund}. Gesucht wurde mit den übrigen Quellen.</p>{/each}
    <Vergleichstabelle {zeilen} gesperrt={speichert} onwahl={waehle} />
    {#if !w.ziel.sofort}<p class="leise"><Symbol name="circle-info" /> Kommt ins Formular, ins Buch erst mit Speichern.</p>{/if}
    {#if vorschlag.raw && Object.keys(vorschlag.raw).length}<Rohdaten daten={vorschlag.raw} gewaehlt={listen} onwahl={(name, an) => (listen = an ? [...listen, name] : listen.filter((l) => l !== name))} />{/if}
  {/if}
  {#snippet fuss()}
    <div class="fensterfuss">
      <span class="tasten2">
        <Knopf text="Verwerfen" symbol="xmark" onclick={() => w.schliesse()} />
        <Knopf text={zahlGewaehlt ? `${anzahl(zahlGewaehlt, "Feld", "Felder")} übernehmen` : "Nichts gewählt"} symbol="check" haupt gesperrt={!zahlGewaehlt} laeuft={speichert} onclick={() => void uebernimm()} />
      </span>
    </div>
  {/snippet}
</Fenster>
