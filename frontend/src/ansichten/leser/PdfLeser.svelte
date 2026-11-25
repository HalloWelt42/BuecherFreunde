<script lang="ts">
  // PDF: Seiten als Bild mit wählbarem Text, oder als umfließender Text; geblättert oder gescrollt
  import { onDestroy, untrack } from "svelte";
  import { dateiUrl, volltextSuche } from "../../lib/api/books";
  import { blaettertaste } from "../../lib/leser/blaettertasten";
  import { FARBTHEMEN, istDunkel, PAPIERFARBEN, papierOder, vorgabeThema, type Papier } from "../../lib/leser/darstellung";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import { ladefehler, type Ladefehler } from "../../lib/leser/ladefehler";
  import { leseart } from "../../lib/leser/leseart.svelte";
  import { ladePdf, verzeichnis, type PdfBuch } from "../../lib/leser/pdf/dokument";
  import { Pdfquelle } from "../../lib/leser/pdf/lesequelle";
  import type { Randeintrag } from "../../lib/leser/randmarken";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import { Gedruckt } from "../../lib/leser/pdf/gedruckt.svelte";
  import { ansichtFuer, ansichtOder, artVon, naechsteStufe, STUFEN, type Ansicht } from "../../lib/leser/pdf/zoom";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { gemerkt, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung } from "../../lib/stand/darstellung.svelte";
  import { geraet } from "../../lib/stand/geraet.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Fussleiste from "./Fussleiste.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import PdfDarstellung from "./PdfDarstellung.svelte";
  import PdfSeiten from "./PdfSeiten.svelte";
  import Seitenstand from "./Seitenstand.svelte";
  import Textansicht from "./Textansicht.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  // Das Gerät zählt beim Öffnen: Telefon und Rechner merken Ansicht und Zoom getrennt
  const telefon = geraet.telefon;
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(buch.reading_position)));
  const meine = telefon ? (alt.telefon ?? {}) : alt;
  const start = untrack(() => ziel);
  const speicher = new Positionsspeicher(untrack(() => buch.id), "pdf");
  const gedruckt = new Gedruckt(untrack(() => buch.id));
  const ersteAnsicht = ansichtOder(start.ansicht || meine.ansicht, ansichtFuer(leseart.blatt.art, telefon));

  let pdf = $state.raw<PdfBuch | null>(null);
  let fehler = $state<Ladefehler | null>(null);
  let seite = $state(start.seite || alt.page || 1);
  let ansicht = $state<Ansicht>(ersteAnsicht);
  // Von Hand gewähltes Maß; null passt die Seite ein
  let zoom = $state<number | null>(ersteAnsicht === "scroll" ? (start.zoom || meine.zoom || 100) / 100 : null);
  let mass = $state(1);
  let papierWahl = $state(start.papier || alt.papier || "");
  let nurText = $state(telefon ? textansicht.an : (start.ansicht || alt.ansicht) === "text");
  // Nur was für dieses Buch von Hand gewählt wurde, wird mit ihm gemerkt: Telefon und Rechner überschreiben einander nicht
  let ansichtGewaehlt = $state(false);
  let fundstelle = $state(start.stelle || start.wort);
  let fundseite = $state(start.seite);
  let textstand = $state({ amAnfang: true, amEnde: false, innen: 0 });
  let rest = $state({ oben: false, unten: false });
  let seiten: PdfSeiten | undefined = $state();
  let text: Textansicht | undefined = $state();
  // Zuletzt gewählte Ansicht jeder Art, damit hin und zurück wieder dieselbe kommt
  const letzte: Partial<Record<Leseart, Ansicht>> = { [artVon(ersteAnsicht)]: ersteAnsicht };

  let papier = $derived<Papier>(papierOder(papierWahl, darstellung.dunkel));
  let farben = $derived(nurText ? textansicht.thema(vorgabeThema(darstellung.dunkel)) : PAPIERFARBEN[papier]);
  let art = $derived(nurText ? leseart.blatt.art : artVon(ansicht));
  let gesamt = $derived(pdf?.seiten ?? buch.page_count);
  let anteil = $derived(nurText ? (seite - 1 + textstand.innen) / Math.max(1, gesamt) : gesamt > 1 ? (seite - 1) / (gesamt - 1) : 0);

  async function lade() {
    fehler = null;
    try {
      const geladen = await ladePdf(buch.id);
      if (!start.seite && start.wort) await sucheSeite();
      seite = Math.min(Math.max(1, seite), geladen.seiten);
      pdf = geladen;
      sitzung.quelle = new Pdfquelle(buch.id, geladen, () => sitzung.kapitel, () => sitzung.kapitelJetzt, () => (nurText ? (text ?? null) : (seiten ?? null)));
      sitzung.rand = {
        anteil: (e) => {
          const s = seiteVon(e);
          return s ? (s - 1) / Math.max(1, gesamt - 1) : null;
        },
        lage: (e) => {
          const s = seiteVon(e);
          return s ? ((nurText ? text : seiten)?.lage(s, e) ?? null) : null;
        },
        kante: () => (nurText ? text : seiten)?.kante() ?? null,
      };
      const ansicht = () => (nurText ? text?.hilfeort : seiten?.hilfeort);
      sitzung.hilfe = {
        blatt: () => ansicht()?.blatt() ?? null,
        zeilenhoehe: () => ansicht()?.zeilenhoehe() ?? 20,
        absatzBei: (x, y) => ansicht()?.absatzBei(x, y) ?? null,
        vorgelesen: () => ansicht()?.vorgelesen() ?? { absatz: null, zeile: null },
        get mitAbsaetzen() {
          return nurText;
        },
        rolle: (px) => ansicht()?.rolle(px) ?? false,
        blaettere: () => ansicht()?.blaettere() ?? false,
        art: () => art,
      };
      sitzung.farbwahl = { jetzt: () => farben, setze: setzeFarben };
      sitzung.kapitel = await verzeichnis(geladen.doc);
    } catch {
      fehler = await ladefehler(buch.id);
    }
  }

  // ?q ohne Seite: auf die erste Seite, die den Begriff enthält
  async function sucheSeite() {
    const wort = start.wort.replace(/"/g, "");
    const treffer = await volltextSuche(buch.id, wort, { limit: 1 }).catch(() => null);
    const nr = treffer?.treffer[0]?.seite;
    if (nr) [seite, fundseite] = [nr, nr];
  }

  // Voreinstellung: in der Textansicht das nächste Farbthema, im Original das Papier, das am besten passt
  function setzeFarben(fg: string, bg: string) {
    const n = FARBTHEMEN.findIndex((t) => t.bg.toLowerCase() === bg.toLowerCase());
    if (nurText) textansicht.setzeThema(n >= 0 ? n : istDunkel(bg) ? 3 : 0);
    else {
      papierWahl = !istDunkel(bg) ? (n === 1 ? "sepia" : "normal") : n === 4 ? "kontrast" : "dunkel";
      merke();
    }
    void fg;
  }

  const seiteVon = (e: Randeintrag) => e.seite ?? (e.prozent !== null ? Math.max(1, Math.round((e.prozent / 100) * gesamt)) : null);

  function gelesen(nr: number) {
    seite = nr;
    merke();
    sitzung.bewegt();
  }

  function merke() {
    const meinStand = { ansicht: telefon ? ansicht : nurText ? "text" : ansicht, zoom: ansicht === "scroll" ? Math.round((zoom ?? mass) * 100) : meine.zoom };
    const werte: Lesewerte = { ...alt, page: seite, ...(papierWahl ? { papier: papierWahl } : {}) };
    if (telefon && ansichtGewaehlt) werte.telefon = meinStand;
    if (!telefon) Object.assign(werte, ansichtGewaehlt || alt.ansicht ? meinStand : {});
    Object.assign(alt, werte);
    const inAdresse = ansichtGewaehlt && !telefon;
    speicher.merke(werte, { page: seite > 1 ? seite : undefined, ansicht: inAdresse && ansicht !== "scroll" ? ansicht : undefined, zoom: inAdresse && ansicht === "scroll" && mass !== 1 ? Math.round(mass * 100) : undefined, papier: papierWahl || undefined });
  }

  function geheZu(nr: number) {
    if (nr >= 1 && nr <= gesamt) gelesen(nr);
  }

  const vor = () => void (nurText ? text?.vor() : seiten?.vor());
  const zurueck = () => void (nurText ? text?.zurueck() : seiten?.zurueck());

  function nimmAnsicht(neu: Ansicht) {
    zoom = neu === "scroll" ? mass : null;
    ansicht = neu;
    letzte[artVon(neu)] = neu;
  }

  function setzeAnsicht(neu: Ansicht | "text") {
    ansichtGewaehlt = true;
    nurText = neu === "text";
    if (telefon) textansicht.an = nurText;
    if (neu !== "text") nimmAnsicht(neu);
    merke();
  }

  /** Hin und her zwischen Original und Text; die Ansicht des Originals bleibt */
  const schalteText = () => setzeAnsicht(nurText ? ansicht : "text");

  function setzeArt(neu: Leseart) {
    leseart.blatt.setze(neu);
    if (artVon(ansicht) !== neu) nimmAnsicht(letzte[neu] ?? ansichtFuer(neu, telefon));
    // Ein Buch mit eigener Ansicht behält seine eigene; alle anderen folgen der Wahl des Geräts
    if (meine.ansicht) ansichtGewaehlt = true;
    merke();
  }

  function setzeZoom(neu: number) {
    ansichtGewaehlt = true;
    if (artVon(ansicht) === "blaettern") {
      const ganz = seiten?.passend(ansicht) ?? null;
      zoom = ganz !== null && neu <= ganz + 0.005 ? null : neu;
      return;
    }
    // Am Telefon rastet die Seitenbreite ein, statt darunter weiterzugehen
    const breit = seiten?.passend("breite") ?? null;
    if (telefon && breit !== null && neu <= breit) return setzeAnsicht("breite");
    ansicht = "scroll";
    zoom = neu;
    letzte.scrollen = "scroll";
    merke();
  }

  const zoome = (richtung: 1 | -1) => setzeZoom(naechsteStufe(mass, richtung));
  const zoomtaste = (richtung: 1 | -1) => (nurText ? undefined : () => zoome(richtung));

  const griffe: Lesegriffe = {
    zumKapitel: (k) => geheZu(k.ziel as number),
    zurMarkierung: (m) => geheZu(Number(m.cfi_range.match(/^page:(\d+)/)?.[1] ?? seite)),
    zurStelle: (ort, cfi) => {
      const nr = Number(cfi.match(/^page:(\d+)/)?.[1] ?? ort.match(/\d+/)?.[0] ?? 0);
      if (nr) geheZu(nr);
      return nr > 0;
    },
    zeichne: () => (nurText ? text?.zeichne() : seiten?.zeichne()),
    hier: () => ({ ort: schreibweise.seite(seite), prozent: gesamt ? (seite / gesamt) * 100 : 0, cfi: `page:${seite}` }),
  };
  untrack(() => (sitzung.griffe = griffe));

  const abwahl = () => getSelection()?.removeAllRanges();

  // Die Fundstelle ist ein Hinweis beim Ankommen, keine Markierung: weg, sobald man weiterliest
  $effect(() => {
    if (!fundstelle || Math.abs(seite - fundseite) <= 1) return;
    fundstelle = "";
    untrack(() => griffe.zeichne());
  });

  // Kapitel, in dem man gerade ist
  $effect(() => {
    sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as number) <= seite);
  });

  $effect(() => {
    const [p, nr] = [pdf, seite];
    return untrack(() => gedruckt.folge(p, nr));
  });

  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    if (vorlesen.quelle && vorlesen.quelle === sitzung.quelle) vorlesen.halt();
    void pdf?.doc.loadingTask.destroy();
    sitzung.griffe = null;
    sitzung.quelle = null;
    sitzung.rand = null;
    sitzung.hilfe = null;
    sitzung.farbwahl = null;
  });

  void lade();
</script>

<svelte:window onkeydown={(e) => blaettertaste(e, art, { vor, zurueck, anfang: () => geheZu(1), ende: () => geheZu(gesamt), groesser: zoomtaste(1), kleiner: zoomtaste(-1) })} />

<Leserahmen {sitzung} {papier} {art} satz={nurText} onart={setzeArt} grund={farben.bg} tinte={farben.fg} bereit={!!pdf} {onzurueck} onabwahl={abwahl}>
  {#if !pdf}
    <Ladehinweis {fehler} adresse={dateiUrl(buch.id)} name={buch.file_name || buch.title} onerneut={() => void lade()} />
  {:else if nurText}
    <Textansicht bind:this={text} {sitzung} {art} startSeite={seite} {fundstelle} grund={farben.bg} tinte={farben.fg} onstand={(s) => { textstand = s; if (s.seite !== seite) gelesen(s.seite); }} onoriginal={schalteText} onmitte={() => sitzung.tippeMitte()} belegt={(p) => sitzung.belegt(p)} onbeschriftet={() => (sitzung.quelle as Pdfquelle | null)?.gezeichnet()} />
  {:else}
    <PdfSeiten bind:this={seiten} {sitzung} {pdf} {ansicht} {zoom} {seite} {fundstelle} {fundseite} onseite={gelesen} onmass={(m) => (mass = m)} onrest={(r) => (rest = r)} onbeschriftet={(nr) => (sitzung.quelle as Pdfquelle | null)?.gezeichnet(nr)} />
  {/if}

  {#snippet darstellung()}
    <PdfDarstellung {ansicht} {nurText} {mass} {papier} stufen={STUFEN} onansicht={setzeAnsicht} onzoom={zoome} onoriginalgroesse={() => setzeZoom(1)} onpapier={(p) => { papierWahl = p; merke(); }} />
  {/snippet}

  {#snippet fuss()}
    <Fussleiste {anteil} anAnfang={nurText ? textstand.amAnfang : seite <= 1 && !rest.oben} amEnde={nurText ? textstand.amEnde : seite >= gesamt && !rest.unten} onzurueck={zurueck} onvor={vor} onanteil={(a) => geheZu(Math.round(1 + a * (gesamt - 1)))} schalter={geraet.telefon ? umschalter : undefined}>
      <Seitenstand {seite} {gesamt} gedruckt={gedruckt.zahl} onseite={geheZu} />
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet umschalter()}
  <Knopf klasse="umschalter" text={nurText ? "Original" : "Text"} symbol={nurText ? "file-pdf" : "align-left"} titel={nurText ? "Seiten des Originals" : "Als Text lesen"} klein onclick={schalteText} />
{/snippet}
