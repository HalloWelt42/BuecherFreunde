<script lang="ts">
  // EPUB und MOBI: umbrochene Kapitel, eigene Schrift und Farben
  import { onDestroy, onMount, untrack } from "svelte";
  import { dateiUrl } from "../../lib/api/books";
  import { schreibtGerade } from "../../lib/flucht";
  import { nimmAuswahl } from "../../lib/leser/auswahl";
  import { BREITE_EINS, BREITE_ZWEI, GROESSE, klemme, oderVorgabe, vorgabeThema, ZEILEN } from "../../lib/leser/darstellung";
  import { EpubAnzeige, type Epubstand } from "../../lib/leser/epub/anzeige";
  import { breite, randfarbe, type Epubdarstellung } from "../../lib/leser/epub/stile";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { wischen } from "../../lib/leser/wischen";
  import { gemerkt, nenntStelle, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung as app } from "../../lib/stand/darstellung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import EpubDarstellung from "./EpubDarstellung.svelte";
  import Fussleiste from "./Fussleiste.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import Trefferleiste from "./Trefferleiste.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  const start = untrack(() => ziel);
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(buch.reading_position)));
  const speicher = new Positionsspeicher(untrack(() => buch.id), "epub");

  // Eigene Farben nur, wenn sie je gewählt wurden; sonst folgt das Buch der App
  let eigeneFarben = $state(!!(alt.fgColor && alt.bgColor));
  let w = $state<Epubdarstellung>({
    groesse: oderVorgabe(alt.fontSize, GROESSE), schrift: alt.fontFamily ?? "", zeilen: oderVorgabe(alt.lineHeight, ZEILEN),
    fg: alt.fgColor ?? "", bg: alt.bgColor ?? "", randTransparent: alt.randTransparent ?? false, blattTransparent: alt.blattTransparent ?? false,
    einseitig: alt.singlePage ?? false, breiteEins: oderVorgabe(alt.maxWidthSingle, BREITE_EINS), breiteZwei: oderVorgabe(alt.maxWidthDouble, BREITE_ZWEI),
  });
  let thema = $derived(vorgabeThema(app.dunkel));
  let d = $derived<Epubdarstellung>({ ...w, fg: eigeneFarben ? w.fg : thema.fg, bg: eigeneFarben ? w.bg : thema.bg });

  let flaeche: HTMLElement | undefined = $state();
  let bereit = $state(false);
  let fehler = $state("");
  let stand = $state<Epubstand>({ anteil: alt.percent ? alt.percent / 100 : 0, cfi: "", kapitel: "", kapitelNr: -1, gedruckt: "" });
  let treffer = $state(0);
  let trefferNr = $state(-1);
  let anzeige: EpubAnzeige | null = null;

  let prozent = $derived(Math.round(stand.anteil * 100));

  async function lade() {
    if (!flaeche) return;
    fehler = "";
    anzeige?.schliesse();
    anzeige = new EpubAnzeige(flaeche, d, { beiStand: gerueckt, beiAuswahl: (a) => nimmAuswahl(sitzung, a && { ...a, ort: schreibweise.prozent(prozent) }) && abwahl(), beiTaste: taste });
    try {
      const cfi = nenntStelle(start) ? start.cfi : (alt.cfi ?? "");
      const gedacht = nenntStelle(start) ? start.prozent : cfi ? 0 : (alt.percent ?? 0);
      const mitte = gedacht / 100 || (start.seite > 0 && buch.page_count > 0 ? (start.seite - 1) / buch.page_count : 0);
      await anzeige.oeffne(buch.id, cfi);
      sitzung.kapitel = anzeige.kapitel;
      bereit = true;
      if (mitte > 0) await anzeige.zuAnteil(mitte);
      void anzeige.zeichne(sitzung.markierungen);
      if (start.wort) await suche(start.wort, mitte);
    } catch (e) {
      fehler = e instanceof Error ? e.message : "Das Buch ließ sich nicht laden";
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

  function gerueckt(s: Epubstand) {
    stand = s;
    sitzung.kapitelJetzt = s.kapitelNr;
    sitzung.auswahl = null;
    if (bereit) merke();
  }

  function merke() {
    const farben = eigeneFarben ? { fgColor: w.fg, bgColor: w.bg } : {};
    speicher.merke({
      cfi: stand.cfi, percent: prozent, fontSize: w.groesse, fontFamily: w.schrift, lineHeight: w.zeilen, ...farben,
      maxWidthSingle: w.breiteEins, maxWidthDouble: w.breiteZwei, singlePage: w.einseitig, randTransparent: w.randTransparent, blattTransparent: w.blattTransparent,
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
    const neu = { ...d };
    void [neu.einseitig, neu.breiteEins, neu.breiteZwei];
    if (bereit) untrack(() => anzeige?.mass(neu));
  });

  const vor = () => void anzeige?.vor();
  const zurueck = () => void anzeige?.zurueck();
  const abwahl = () => anzeige?.waehleAb();

  function taste(e: KeyboardEvent) {
    if (schreibtGerade(e) || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
    const groesser = (schritt: number) => setze({ groesse: klemme(w.groesse + schritt, GROESSE) });
    const griff: Record<string, () => void> = { ArrowRight: vor, PageDown: vor, ArrowLeft: zurueck, PageUp: zurueck, "+": () => groesser(10), "=": () => groesser(10), "-": () => groesser(-10) };
    const tun = griff[e.key];
    if (!tun) {
      // Esc im Kapitelrahmen soll dieselben Felder schließen wie außerhalb
      if (e.key === "Escape" && e.view !== window) document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      return;
    }
    e.preventDefault();
    tun();
  }

  const griffe: Lesegriffe = {
    abschnittName: "Kapitel",
    abschnitt: async () => anzeige?.kapiteltext() ?? "",
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

  $effect(() => {
    if (flaeche) return wischen(flaeche, { links: vor, rechts: zurueck });
  });

  onMount(() => void lade());
  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    anzeige?.schliesse();
    sitzung.griffe = null;
  });
</script>

<svelte:window onkeydown={taste} />

<Leserahmen {sitzung} {bereit} {onzurueck} onabwahl={abwahl} treffer={treffer ? trefferleiste : undefined}>
  <div class="epubflaeche" class:ohne-grund={d.randTransparent && d.blattTransparent} style:--lesebreite="{breite(d)}px" style:background={randfarbe(d)} bind:this={flaeche}></div>
  {#if !bereit}<Ladehinweis {fehler} adresse={dateiUrl(buch.id)} name={buch.file_name || buch.title} onerneut={() => void lade()} />{/if}

  {#snippet darstellung()}<EpubDarstellung {d} onwahl={setze} />{/snippet}

  {#snippet fuss()}
    <Fussleiste anteil={stand.anteil} onzurueck={zurueck} onvor={vor} onanteil={(a) => void anzeige?.zuAnteil(a)}>
      {#if stand.kapitel}<span class="klein kapitel" title={stand.kapitel}>{stand.kapitel}</span>{/if}
      <span class="stand zahl klein">{prozent} %{stand.gedruckt ? `, gedruckt ${stand.gedruckt}` : ""}</span>
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet trefferleiste()}
  <Trefferleiste wort={start.wort} nr={trefferNr} gesamt={treffer} onspringe={(n) => void zumTreffer(n)} onschliessen={sucheZu} />
{/snippet}
