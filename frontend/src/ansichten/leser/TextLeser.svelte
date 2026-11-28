<script lang="ts">
  // Text und Markdown auf einem Blatt, geblättert oder gescrollt
  import "../../stil/lesetext.css";
  import { onDestroy, setContext, tick, untrack } from "svelte";
  import { anfrage } from "../../lib/api/client";
  import { formatName } from "../../lib/format";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { blaettergesten } from "../../lib/leser/blaettergesten";
  import { blaettertaste } from "../../lib/leser/blaettertasten";
  import { blattrand } from "../../lib/leser/blattrand.svelte";
  import { GROESSE, istDunkel, klemme, oderVorgabe, vorgabeThema, ZEILEN } from "../../lib/leser/darstellung";
  import { Textfluss } from "../../lib/leser/fluss/textfluss";
  import { ladefehler, type Ladefehler } from "../../lib/leser/ladefehler";
  import { leseart } from "../../lib/leser/leseart.svelte";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { kannHervorheben, Rechteckschicht } from "../../lib/leser/hervorhebung";
  import { setzeCode } from "../../lib/leser/text/codefarben";
  import { Blattquelle } from "../../lib/leser/text/lesequelle";
  import { nutzeSchrift } from "../../lib/leser/schriften";
  import { absatzBei, vorgelesenIn } from "../../lib/leser/fokus";
  import { lesehilfen } from "../../lib/leser/lesehilfen.svelte";
  import { imBlick, sichtVon, zeichenRechteck } from "../../lib/leser/mitlauf";
  import { rechteckeVon } from "../../lib/leser/festbereich";
  import type { Randeintrag } from "../../lib/leser/randmarken";
  import { prozentVon, textkapitel, zeichneMarkierungen, zeichneTreffer } from "../../lib/leser/text/markierung";
  import { schreibweise, type Kapitel } from "../../lib/leser/typen";
  import { gemerkt, nenntStelle, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung as app } from "../../lib/stand/darstellung.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Fussleiste from "./Fussleiste.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import Markdown from "./Markdown.svelte";
  import Schlichttext from "./Schlichttext.svelte";
  import Seitenstand from "./Seitenstand.svelte";
  import TextDarstellung, { type Textdarstellung } from "./TextDarstellung.svelte";
  import Trefferleiste from "./Trefferleiste.svelte";
  import { Codestellenstand, listingAus } from "../../lib/leser/codestellen.svelte";
  import { codebloecke, codezeilen, type Zeilenorte } from "../../lib/leser/text/codeorte";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { ausfuehren } from "../../lib/stand/ausfuehren.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  const ZEICHEN_JE_SEITE = 2000;
  const start = untrack(() => ziel);
  // Was gelesen wird (lib/leser/lesefassung): das Original, ein weiteres Format oder Begleitmaterial
  const fassung = untrack(() => sitzung.fassung);
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(fassung.position)));
  const speicher = new Positionsspeicher(fassung.ort, "txt");
  const istMarkdown = fassung.format === "md";

  let eigeneFarben = $state(!!(alt.fgColor && alt.bgColor));
  let w = $state<Textdarstellung>({
    groesse: oderVorgabe(alt.fontSize, GROESSE), schrift: alt.fontFamily ?? "", zeilen: oderVorgabe(alt.lineHeight, ZEILEN),
    fg: alt.fgColor ?? "", bg: alt.bgColor ?? "", durchsichtig: alt.blattTransparent ?? false,
  });
  let thema = $derived(vorgabeThema(app.dunkel));
  let d = $derived<Textdarstellung>({ ...w, fg: eigeneFarben ? w.fg : thema.fg, bg: eigeneFarben ? w.bg : thema.bg });
  let art = $derived(leseart.blatt.art);

  let inhalt = $state<string | null>(null);

  // Codestellen mit Taste, nur mit der Sandbox (BF-29): in Markdown die Codeblöcke, im Text die erste Zeile der Stelle
  const codestellen = untrack(() => anschluesse.jetzt.ausfuehren) && fassung.mitBuchtext ? new Codestellenstand(untrack(() => buch.id), false) : null;
  const zeilenorte = new Map<string, Zeilenorte>();
  $effect(() => {
    if (!codestellen || inhalt === null) return;
    codestellen.lade();
    const stellen = codestellen.alle;
    const zeilen = inhalt ? inhalt.split("\n").length : 1;
    sitzung.code = !stellen.length ? null : {
      orte: () => (!satz ? [] : istMarkdown ? codebloecke(satz, stellen) : codezeilen(satz, stellen, zeilenorte)),
      oeffne: (s) => ausfuehren.oeffne(listingAus(s, buch, `/book/${buch.id}/read?percent=${Math.round((((s.teile[0]?.zeile ?? 1) - 1) / zeilen) * 1000) / 10}`)),
    };
  });
  let fehler = $state<Ladefehler | null>(null);
  let flaeche: HTMLElement | undefined = $state();
  let blatt: HTMLElement | undefined = $state();
  let satz: HTMLElement | undefined = $state();
  let fluss: Textfluss | null = null;
  let stand = $state({ anteil: 0, amAnfang: true, amEnde: false });
  let trefferliste = $state.raw<StaticRange[]>([]);
  let markiert = new Map<number, StaticRange>();
  let ersatz: Rechteckschicht | undefined;
  let quelle: Blattquelle | null = null;
  let trefferNr = $state(-1);

  let gesamt = $derived(fassung.mitBuchtext && buch.page_count > 1 ? buch.page_count : Math.max(1, Math.ceil((inhalt?.length ?? 0) / ZEICHEN_JE_SEITE)));
  let seite = $derived(Math.max(1, Math.min(gesamt, Math.ceil(stand.anteil * gesamt) || 1)));

  async function lade() {
    fehler = null;
    try {
      inhalt = await (await anfrage(fassung.datei)).text();
    } catch {
      fehler = await ladefehler(fassung.datei);
    }
  }

  /** Wird gerufen, sobald der Text auf dem Blatt steht */
  async function steht() {
    await tick();
    // Erst die Codeblöcke fertig setzen: das Färben tauscht ihre Textknoten aus, auf denen alles Weitere aufbaut (BF-54)
    if (istMarkdown && satz) await setzeCode(satz);
    if (!flaeche || !blatt || !satz) return;
    const s = satz;
    sitzung.kapitel = sammleKapitel();
    if (!kannHervorheben()) ersatz ??= new Rechteckschicht(blatt);
    zeichne();
    fluss ??= new Textfluss({ flaeche, blatt, satz }, art, bewegt);
    const ab = start.prozent ? start.prozent / 100 : start.seite ? (start.seite - 1) / gesamt : nenntStelle(start) ? 0 : (alt.scrollPct ?? 0) / 100;
    fluss.zuAnteil(ab);
    quelle = new Blattquelle({ satz: s, flaeche, fluss: () => fluss, kapitel: () => sitzung.kapitel, kapitelJetzt: () => sitzung.kapitelJetzt, ersatz: () => ersatz, ohneTitel: (nr, alle) => `Stück ${nr + 1} von ${alle}` });
    sitzung.quelle = quelle;
    sitzung.hilfe = {
      blatt: () => blatt?.getBoundingClientRect() ?? null,
      zeilenhoehe: () => (blatt ? Number.parseFloat(getComputedStyle(blatt).lineHeight) || 24 : 24),
      absatzBei: (x, y) => (satz ? absatzBei(document, x, y, satz) : null),
      vorgelesen: () => vorgelesenIn(document, satz ?? null),
      mitAbsaetzen: true,
      rolle: (px) => {
        const vorher = flaeche!.scrollTop;
        flaeche!.scrollTop += px;
        return flaeche!.scrollTop !== vorher;
      },
      blaettere: () => fluss?.vor() ?? false,
      art: () => art,
    };
    sitzung.farbwahl = { jetzt: () => ({ fg: d.fg, bg: d.bg }), setze: (fg, bg) => setze({ fg, bg }) };
    sitzung.rand = { anteil: (e) => (e.prozent !== null ? e.prozent / 100 : null), lage: lageAmRand, kante: () => blatt?.getBoundingClientRect().right ?? null, stand: () => stand.anteil };
    if (start.wort || start.stelle) zeigeTreffer(start.wort || start.stelle, ab);
  }

  function sammleKapitel(): Kapitel[] {
    if (!satz) return [];
    if (istMarkdown) return [...satz.querySelectorAll<HTMLElement>("h1, h2, h3, h4")].map((h) => ({ titel: h.textContent?.trim() || "Ohne Titel", tiefe: Number(h.tagName[1]) - 1, ziel: h }));
    return textkapitel((inhalt ?? "").split("\n")).map((k) => ({ titel: k.titel, tiefe: 0, ziel: k.anteil }));
  }

  function zeigeTreffer(wort: string, ab: number) {
    if (!satz || !fluss) return;
    trefferliste = zeichneTreffer(satz, wort, 500, ersatz);
    if (!trefferliste.length) return;
    const nr = ab > 0 ? trefferliste.findIndex((t) => fluss!.anteilVon(t.startContainer, t.startOffset) >= ab - 0.002) : 0;
    zumTreffer(Math.max(0, nr));
  }

  function zumTreffer(nr: number) {
    trefferNr = (nr + trefferliste.length) % trefferliste.length;
    fluss?.zu(trefferliste[trefferNr]);
  }

  function trefferZu() {
    if (satz) zeichneTreffer(satz, "", 0, ersatz);
    trefferliste = [];
  }

  function bewegt() {
    if (!fluss) return;
    stand = { anteil: fluss.anteil, amAnfang: fluss.amAnfang, amEnde: fluss.amEnde };
    if (istMarkdown) sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => fluss!.erreicht(k.ziel as HTMLElement));
    else sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as number) <= stand.anteil + 0.002);
    ersatz?.zeichne();
    sitzung.bewegt();
    merke();
  }

  // Für die Marken am Rand: wo eine Stelle auf dem Schirm steht
  function lageAmRand(e: Randeintrag): number | null {
    if (!flaeche || !blatt || !fluss) return null;
    const b = blatt.getBoundingClientRect();
    const sicht = art === "blaettern" ? { oben: b.top, unten: b.bottom, links: b.left, rechts: b.right } : sichtVon(flaeche);
    const r = e.art === "Markierung" ? markiert.get((e.quelle as { id: number }).id) : null;
    if (r?.startContainer.isConnected) return imBlick(r, sicht) ? (rechteckeVon(r)[0]?.top ?? null) : null;
    const a = e.prozent !== null ? fluss.ankerBei(e.prozent / 100) : null;
    const q = a?.knoten.nodeType === Node.TEXT_NODE ? zeichenRechteck(a.knoten as Text, a.versatz) : null;
    return q && q.bottom > sicht.oben && q.top < sicht.unten && q.right > sicht.links && q.left < sicht.rechts ? q.top : null;
  }

  function zeichne() {
    if (satz) markiert = zeichneMarkierungen(satz, sitzung.markierungen, ersatz);
  }

  function merke() {
    const farben = eigeneFarben ? { fgColor: w.fg, bgColor: w.bg } : {};
    const prozent = Math.round(stand.anteil * 1000) / 10;
    speicher.merke({ scrollPct: prozent, fontSize: w.groesse, fontFamily: w.schrift, lineHeight: w.zeilen, ...farben, blattTransparent: w.durchsichtig }, { percent: prozent > 0 ? prozent : undefined });
  }

  function setze(neu: Partial<Textdarstellung>) {
    const tun = async () => {
      if (neu.fg || neu.bg) {
        Object.assign(w, { fg: d.fg, bg: d.bg });
        eigeneFarben = true;
      }
      Object.assign(w, neu);
      await tick();
    };
    void (fluss ? fluss.halte(tun) : tun());
    merke();
  }

  $effect(() => {
    const neu = art;
    untrack(() => fluss?.setzeArt(neu));
  });

  $effect(() => {
    if (d.schrift) nutzeSchrift(d.schrift);
  });

  // Anderer Rand: dieselbe Stelle bleibt
  $effect(() => {
    void [blattrand.wert, schale.vollbild, lesehilfen.wirksam];
    untrack(() => void fluss?.halte(tick));
  });

  const vor = () => void fluss?.vor();
  const zurueck = () => void fluss?.zurueck();
  const abwahl = () => getSelection()?.removeAllRanges();
  const groesser = (schritt: number) => setze({ groesse: klemme(w.groesse + schritt, GROESSE) });
  const tasten = { vor, zurueck, anfang: () => fluss?.zuAnteil(0), ende: () => fluss?.zuAnteil(1), groesser: () => groesser(10), kleiner: () => groesser(-10) };

  // Sprungmarken im Text
  setContext("lesesprung", (kennung: string) => {
    const e = document.getElementById(kennung);
    if (e) fluss?.zu(e);
  });

  const griffe: Lesegriffe = {
    zumKapitel: (k) => (k.ziel instanceof HTMLElement ? fluss?.zu(k.ziel) : fluss?.zuAnteil(k.ziel as number)),
    zurMarkierung: (m) => {
      const gezeichnet = markiert.get(m.id);
      if (gezeichnet?.startContainer.isConnected) fluss?.zu(gezeichnet);
      else fluss?.zuAnteil((prozentVon(m.cfi_range) ?? 0) / 100);
    },
    zurStelle: (ort, cfi, p) => {
      const prozent = p || (prozentVon(cfi) ?? (Number(ort.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".")) || 0));
      const nr = Number(ort.match(/(\d+)/)?.[1]) || 0;
      if (!prozent && !nr) return false;
      fluss?.zuAnteil(prozent ? prozent / 100 : (nr - 1) / gesamt);
      return true;
    },
    zeichne,
    hier: () => ({ ort: schreibweise.seite(seite), prozent: Math.round(stand.anteil * 1000) / 10, cfi: `percent:${(stand.anteil * 100).toFixed(1)}` }),
  };
  untrack(() => (sitzung.griffe = griffe));

  $effect(() => {
    const f = flaeche;
    if (!f || inhalt === null) return;
    const beschreibe = (b: Range) => {
      const anteil = fluss?.anteilVon(b.startContainer, b.startOffset) ?? 0;
      return { cfi: `percent:${(anteil * 100).toFixed(1)}`, ort: schreibweise.seite(Math.max(1, Math.ceil(anteil * gesamt))) };
    };
    return beobachteAuswahl(f, beschreibe, (a) => nimmAuswahl(sitzung, a) && abwahl());
  });

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    return blaettergesten(f, { rahmen: () => f.getBoundingClientRect() }, { gilt: () => art === "blaettern", vor, zurueck, mitte: () => sitzung.tippeMitte(), belegt: (p) => sitzung.belegt(p), klick: () => sitzung.schalteLeisten() });
  });

  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    fluss?.zerstoere();
    quelle?.zerstoere();
    ersatz?.zerstoere();
    if (vorlesen.quelle === quelle && quelle) vorlesen.halt();
    sitzung.griffe = null;
    sitzung.quelle = null;
    sitzung.rand = null;
    sitzung.hilfe = null;
    sitzung.farbwahl = null;
    sitzung.code = null;
    codestellen?.beende();
  });

  void lade();
</script>

<svelte:window onkeydown={(e) => blaettertaste(e, art, tasten)} />

<Leserahmen {sitzung} {art} onart={(a) => leseart.blatt.setze(a)} grund={d.bg} tinte={d.fg} bereit={inhalt !== null} {onzurueck} onabwahl={abwahl} treffer={trefferliste.length ? trefferleiste : undefined}>
  {#if inhalt === null}
    <Ladehinweis {fehler} adresse={fassung.datei} name={fassung.dateiname === true ? buch.title : fassung.dateiname} onerneut={() => void lade()} />
  {:else}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="seiten lesetext textbuch rollen" tabindex="0" role="document" aria-label="Text" bind:this={flaeche}>
      <article class="blatt" class:ohne-grund={d.durchsichtig} class:dunkel={istDunkel(d.bg)} class:markdown={istMarkdown} lang={buch.language || "de"} bind:this={blatt}
        style:--blattgrund={d.durchsichtig ? "transparent" : d.bg} style:--blatttinte={d.fg} style:--lesegroesse="{(1.125 * d.groesse) / 100}rem" style:font-family={d.schrift || undefined} style:line-height={d.zeilen}>
        <div class="satz" bind:this={satz}>
          {#if istMarkdown}<Markdown quelle={inhalt} onsteht={steht} />{:else}<Schlichttext text={inhalt} onsteht={steht} />{/if}
        </div>
      </article>
    </div>
  {/if}

  {#snippet darstellung()}<TextDarstellung {d} onwahl={setze} />{/snippet}

  {#snippet fuss()}
    <Fussleiste {sitzung} anteil={stand.anteil} anAnfang={stand.amAnfang} amEnde={stand.amEnde} onzurueck={zurueck} onvor={vor} onanteil={(a) => fluss?.zuAnteil(a)}>
      <Seitenstand {seite} {gesamt} onseite={(nr) => fluss?.zuAnteil((nr - 1) / gesamt)} />
      <span class="stand zahl klein nur-breit">{Math.round(stand.anteil * 100)} %, {formatName(fassung.format)}</span>
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet trefferleiste()}
  <Trefferleiste wort={start.wort || start.stelle} nr={trefferNr} gesamt={trefferliste.length} onspringe={zumTreffer} onschliessen={trefferZu} />
{/snippet}
