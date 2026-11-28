<script lang="ts">
  // EPUB und MOBI: umbrochene Kapitel, eigene Schrift und Farben
  import { ladefehler, type Ladefehler } from "../../lib/leser/ladefehler";
  import { onDestroy, onMount, untrack } from "svelte";
  import { blaettertaste } from "../../lib/leser/blaettertasten";
  import { nimmAuswahl } from "../../lib/leser/auswahl";
  import { blattrand } from "../../lib/leser/blattrand.svelte";
  import { GROESSE, klemme, oderVorgabe, vorgabeThema, ZEILEN } from "../../lib/leser/darstellung";
  import { blattbreite } from "../../lib/leser/leseraum.svelte";
  import { EpubAnzeige, type Epubstand, type Seitenmass } from "../../lib/leser/epub/anzeige";
  import { breite, randfarbe, type Epubdarstellung } from "../../lib/leser/epub/stile";
  import { leseart } from "../../lib/leser/leseart.svelte";
  import { Epubquelle } from "../../lib/leser/epub/lesequelle";
  import { absatzBei, verschiebe, vorgelesenIn } from "../../lib/leser/fokus";
  import { hilfenEpubCss, lesehilfen } from "../../lib/leser/lesehilfen.svelte";
  import { VORLESESATZ } from "../../lib/leser/text/lesequelle";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { gemerkt, nenntStelle, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung as app } from "../../lib/stand/darstellung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import EpubDarstellung from "./EpubDarstellung.svelte";
  import Fussleiste from "./Fussleiste.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import Trefferleiste from "./Trefferleiste.svelte";
  import { Codestellenstand, listingAus } from "../../lib/leser/codestellen.svelte";
  import { codebloecke } from "../../lib/leser/text/codeorte";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { ausfuehren } from "../../lib/stand/ausfuehren.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  const start = untrack(() => ziel);
  // Original oder Übersetzung (BF-71): Datei, Lesestand und ob Stellen hierher gehören
  const fassung = untrack(() => sitzung.fassung);
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(fassung.position)));
  const speicher = new Positionsspeicher(fassung.ort, "epub");

  // Eigene Farben nur, wenn sie je gewählt wurden; sonst folgt das Buch der App
  let eigeneFarben = $state(!!(alt.fgColor && alt.bgColor));
  let w = $state<Epubdarstellung>({
    groesse: oderVorgabe(alt.fontSize, GROESSE), schrift: alt.fontFamily ?? "", zeilen: oderVorgabe(alt.lineHeight, ZEILEN),
    fg: alt.fgColor ?? "", bg: alt.bgColor ?? "", randTransparent: alt.randTransparent ?? false, blattTransparent: alt.blattTransparent ?? false,
    einseitig: alt.singlePage ?? false,
  });
  let thema = $derived(vorgabeThema(app.dunkel));
  let d = $derived<Epubdarstellung>({ ...w, fg: eigeneFarben ? w.fg : thema.fg, bg: eigeneFarben ? w.bg : thema.bg });

  let art = $derived(leseart.buch.art);
  let mass = $derived<Seitenmass>({ art, rand: blattrand.wert, oben: blattrand.oben(schale.vollbild), spalte: blattbreite.wert });

  let flaeche: HTMLElement | undefined = $state();
  let bereit = $state(false);
  let fehler = $state<Ladefehler | null>(null);
  let stand = $state<Epubstand>({ anteil: alt.percent ? alt.percent / 100 : 0, cfi: "", kapitel: "", kapitelNr: -1, gedruckt: "" });
  let treffer = $state(0);
  let trefferNr = $state(-1);
  let anzeige: EpubAnzeige | null = null;

  // Codestellen mit Taste, nur mit der Sandbox (BF-29): die Codeblöcke in den gezeigten Kapiteln; der Rückweg führt an die
  // Stelle, an der man beim Öffnen las. Sie hängen am Original, nicht an einer Übersetzung.
  const codestellen = untrack(() => anschluesse.jetzt.ausfuehren) && fassung.mitStellen ? new Codestellenstand(untrack(() => buch.id), false) : null;
  $effect(() => {
    if (!codestellen || !bereit) return;
    codestellen.lade();
    const stellen = codestellen.alle;
    sitzung.code = !stellen.length ? null : {
      orte: () => (anzeige?.dokumente() ?? []).flatMap(({ doc, x, y }) => codebloecke(doc, stellen, { x, y })),
      oeffne: (s) => ausfuehren.oeffne(listingAus(s, buch, `/book/${buch.id}/read${stand.cfi ? `?cfi=${encodeURIComponent(stand.cfi)}` : ""}`)),
    };
  });
  let quelle: Epubquelle | null = null;

  let prozent = $derived(Math.round(stand.anteil * 100));

  async function lade() {
    if (!flaeche) return;
    fehler = null;
    anzeige?.schliesse();
    anzeige = new EpubAnzeige(flaeche, d, mass, {
      beiStand: gerueckt, beiTaste: taste, mitte: () => sitzung.tippeMitte(), klick: () => sitzung.schalteLeisten(), belegt: (p) => sitzung.belegt(p), geladen: (doc) => quelle?.geladen(doc), maus: (e) => zeige(e), gerollt: () => sitzung.bewegt(),
      beiAuswahl: (a) => nimmAuswahl(sitzung, a && { ...a, ort: schreibweise.prozent(prozent) }) && abwahl(),
    });
    try {
      const cfi = nenntStelle(start) ? start.cfi : (alt.cfi ?? "");
      const gedacht = nenntStelle(start) ? start.prozent : cfi ? 0 : (alt.percent ?? 0);
      const mitte = gedacht / 100 || (start.seite > 0 && buch.page_count > 0 && fassung.mitBuchtext ? (start.seite - 1) / buch.page_count : 0);
      await anzeige.oeffne(fassung.datei, cfi);
      sitzung.kapitel = anzeige.kapitel;
      const a = anzeige;
      quelle?.zerstoere();
      quelle = new Epubquelle({ view: () => a.ansicht, flaeche, gescrollt: () => art === "scrollen", kapitel: () => sitzung.kapitel, kapitelJetzt: () => sitzung.kapitelJetzt, male: (b) => a.male(b, VORLESESATZ.farbe) });
      sitzung.quelle = quelle;
      const aktuell = () => a.ansicht?.renderer?.getContents()[0];
      const rahmen = () => aktuell()?.doc.defaultView?.frameElement?.getBoundingClientRect();
      sitzung.hilfe = {
        blatt: () => flaeche?.getBoundingClientRect() ?? null,
        zeilenhoehe: () => {
          const b = aktuell()?.doc.body;
          return b ? Number.parseFloat(getComputedStyle(b).lineHeight) || 24 : 24;
        },
        absatzBei: (x, y) => {
          const [g, r] = [aktuell(), rahmen()];
          const k = g?.doc.body && r ? absatzBei(g.doc, x - r.left, y - r.top, g.doc.body) : null;
          return k && verschiebe(k, r!.left, r!.top);
        },
        vorgelesen: () => {
          const [g, r] = [aktuell(), rahmen()];
          return g && r ? vorgelesenIn(g.doc, g.doc.body, { x: r.left, y: r.top }) : { absatz: null, zeile: null };
        },
        mitAbsaetzen: true,
        rolle: (px) => {
          const r = a.ansicht?.renderer as (HTMLElement & { containerPosition: number }) | undefined;
          if (!r) return false;
          const vorher = r.containerPosition;
          r.containerPosition = vorher + px;
          return r.containerPosition !== vorher;
        },
        blaettere: () => {
          const r = a.ansicht?.renderer as { atEnd?: boolean } | undefined;
          if (r?.atEnd) return false;
          a.vor();
          return true;
        },
        art: () => art,
      };
      sitzung.farbwahl = { jetzt: () => ({ fg: d.fg, bg: d.bg }), setze: (fg, bg) => setze({ fg, bg }) };
      sitzung.rand = { anteil: (e) => (e.prozent !== null ? e.prozent / 100 : e.cfi ? a.anteilVon(e.cfi) : null), lage: (e) => (e.cfi ? a.lageVon(e.cfi) : null), kante: () => flaeche?.getBoundingClientRect().right ?? null, stand: () => stand.anteil };
      bereit = true;
      if (mitte > 0) await anzeige.zuAnteil(mitte);
      void anzeige.zeichne(sitzung.markierungen);
      if (start.wort) await suche(start.wort, mitte);
    } catch {
      fehler = await ladefehler(fassung.datei);
    }
  }

  async function suche(wort: string, ab: number) {
    if (!anzeige) return;
    const erster = await anzeige.suche(wort.replace(/^"|"$/g, ""), ab);
    treffer = anzeige.treffer.length;
    if (erster >= 0) await zumTreffer(erster);
    else melde.info(`"${wort}" steht nicht wörtlich im Text`);
  }

  async function zumTreffer(nr: number) {
    trefferNr = (nr + treffer) % treffer;
    await anzeige?.zurStelle(anzeige.treffer[trefferNr]);
  }

  function sucheZu() {
    anzeige?.sucheBeenden();
    [treffer, trefferNr] = [0, -1];
  }

  // Die Maus im Kapitelrahmen: Spieler, Ruhe und Fokus brauchen sie in Lagen des Fensters
  function zeige(e: PointerEvent) {
    sitzung.regt(e);
    if (e.pointerType !== "mouse") return;
    const r = (e.view as Window | null)?.frameElement?.getBoundingClientRect();
    sitzung.zeiger = { x: e.clientX + (r?.left ?? 0), y: e.clientY + (r?.top ?? 0) };
  }

  // Lesehilfen im Kapitel: Abstände, Abbildungen; in Ruhe auch dort kein Zeiger
  $effect(() => {
    const css = hilfenEpubCss(lesehilfen.wirksam) + (sitzung.ruhig ? "\n* { cursor: none !important; }" : "");
    if (bereit) untrack(() => anzeige?.zusatz(css));
  });

  function gerueckt(s: Epubstand) {
    stand = s;
    sitzung.kapitelJetzt = s.kapitelNr;
    sitzung.auswahl = null;
    if (bereit) merke();
    sitzung.bewegt();
  }

  function merke() {
    const farben = eigeneFarben ? { fgColor: w.fg, bgColor: w.bg } : {};
    speicher.merke({
      cfi: stand.cfi, percent: prozent, fontSize: w.groesse, fontFamily: w.schrift, lineHeight: w.zeilen, ...farben,
      singlePage: w.einseitig, randTransparent: w.randTransparent, blattTransparent: w.blattTransparent,
    }, { cfi: stand.cfi || undefined });
  }

  function setze(neu: Partial<Epubdarstellung>) {
    if (neu.fg || neu.bg) {
      // Wer eine Farbe wählt, hält ab jetzt beide fest
      Object.assign(w, { fg: d.fg, bg: d.bg });
      eigeneFarben = true;
    }
    Object.assign(w, neu);
    merke();
  }

  // Darstellung geändert (auch Hell und Dunkel der App): Stile in die Kapitel, Maß in den Umbruch
  $effect(() => {
    const neu = d;
    if (bereit) anzeige?.stile(neu);
  });
  $effect(() => {
    const [neu, m] = [{ ...d }, mass];
    if (bereit) untrack(() => anzeige?.mass(neu, m));
  });

  const vor = () => void anzeige?.vor();
  const zurueck = () => void anzeige?.zurueck();
  const abwahl = () => anzeige?.waehleAb();

  const groesser = (schritt: number) => setze({ groesse: klemme(w.groesse + schritt, GROESSE) });
  const tasten = { vor, zurueck, zeileVor: () => anzeige?.zeileVor(), zeileZurueck: () => anzeige?.zeileZurueck(), anfang: () => void anzeige?.zuAnteil(0), ende: () => void anzeige?.zuAnteil(1), groesser: () => groesser(10), kleiner: () => groesser(-10) };

  function taste(e: KeyboardEvent) {
    if (blaettertaste(e, art, tasten)) return;
    // Esc im Kapitelrahmen soll dieselben Felder schließen wie außerhalb
    if (e.key === "Escape" && e.view !== window) document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  }

  const griffe: Lesegriffe = {
    zumKapitel: (k) => void anzeige?.springe(k.ziel as string),
    zurMarkierung: (m) => void anzeige?.zurStelle(m.cfi_range),
    zurStelle: (ort, cfi, p) => {
      const anteil = p || Number(ort.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".")) || 0;
      const seite = Number(ort.match(/^(?:S\.)?\s*(\d+)$/)?.[1]) || 0;
      if (cfi.startsWith("epubcfi")) void anzeige?.zurStelle(cfi);
      else if (anteil) void anzeige?.zuAnteil(anteil / 100);
      else if (seite && buch.page_count) void anzeige?.zuAnteil((seite - 1) / buch.page_count);
      else return false;
      return true;
    },
    zeichne: () => void anzeige?.zeichne(sitzung.markierungen),
    hier: () => ({ ort: schreibweise.prozent(prozent), prozent: stand.anteil * 100, cfi: stand.cfi }),
  };
  untrack(() => (sitzung.griffe = griffe));

  onMount(() => void lade());
  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    if (vorlesen.quelle && vorlesen.quelle === quelle) vorlesen.halt();
    quelle?.zerstoere();
    sitzung.quelle = null;
    sitzung.rand = null;
    sitzung.hilfe = null;
    sitzung.farbwahl = null;
    sitzung.code = null;
    codestellen?.beende();
    anzeige?.schliesse();
    sitzung.griffe = null;
  });
</script>

<svelte:window onkeydown={taste} />

<Leserahmen {sitzung} {art} onart={(a) => leseart.buch.setze(a)} grund={d.bg} tinte={d.fg} {bereit} {onzurueck} onabwahl={abwahl} treffer={treffer ? trefferleiste : undefined}>
  <div class="epubflaeche" class:ohne-grund={d.randTransparent && d.blattTransparent} style:--lesebreite="{breite(d, art, blattbreite.wert)}px" style:background={randfarbe(d)} bind:this={flaeche}></div>
  {#if !bereit}<Ladehinweis {fehler} adresse={fassung.datei} name={buch.file_name || buch.title} onerneut={() => void lade()} />{/if}

  {#snippet darstellung()}<EpubDarstellung {d} {art} onwahl={setze} />{/snippet}

  {#snippet fuss()}
    <Fussleiste {sitzung} anteil={stand.anteil} onzurueck={zurueck} onvor={vor} onanteil={(a) => void anzeige?.zuAnteil(a)}>
      {#if stand.kapitel}<span class="klein kapitel" title={stand.kapitel}>{stand.kapitel}</span>{/if}
      <span class="stand zahl klein">{prozent} %{stand.gedruckt ? `, gedruckt ${stand.gedruckt}` : ""}</span>
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet trefferleiste()}
  <Trefferleiste wort={start.wort} nr={trefferNr} gesamt={treffer} onspringe={(n) => void zumTreffer(n)} onschliessen={sucheZu} />
{/snippet}
