<script lang="ts">
  // Text und Markdown auf einem Blatt, geblättert oder gescrollt
  import "../../stil/lesetext.css";
  import { onDestroy, setContext, tick, untrack } from "svelte";
  import { dateiUrl } from "../../lib/api/books";
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
  import { faerbeCode, kopierknoepfe } from "../../lib/leser/text/codefarben";
  import { prozentVon, textkapitel, zeichneMarkierungen, zeichneTreffer } from "../../lib/leser/text/markierung";
  import { schreibweise, type Kapitel } from "../../lib/leser/typen";
  import { gemerkt, nenntStelle, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung as app } from "../../lib/stand/darstellung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Fussleiste from "./Fussleiste.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import Markdown from "./Markdown.svelte";
  import Schlichttext from "./Schlichttext.svelte";
  import Seitenstand from "./Seitenstand.svelte";
  import TextDarstellung, { BREITEN, type Textdarstellung } from "./TextDarstellung.svelte";
  import Trefferleiste from "./Trefferleiste.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  const ZEICHEN_JE_SEITE = 2000;
  const start = untrack(() => ziel);
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(buch.reading_position)));
  const speicher = new Positionsspeicher(untrack(() => buch.id), "txt");
  const istMarkdown = untrack(() => buch.file_format === "md");

  let eigeneFarben = $state(!!(alt.fgColor && alt.bgColor));
  let w = $state<Textdarstellung>({
    groesse: oderVorgabe(alt.fontSize, GROESSE), schrift: alt.fontFamily ?? "", zeilen: oderVorgabe(alt.lineHeight, ZEILEN),
    breite: alt.breite !== undefined && BREITEN[alt.breite] ? alt.breite : 1, fg: alt.fgColor ?? "", bg: alt.bgColor ?? "", durchsichtig: alt.blattTransparent ?? false,
  });
  let thema = $derived(vorgabeThema(app.dunkel));
  let d = $derived<Textdarstellung>({ ...w, fg: eigeneFarben ? w.fg : thema.fg, bg: eigeneFarben ? w.bg : thema.bg });
  let art = $derived(leseart.blatt.art);

  let inhalt = $state<string | null>(null);
  let fehler = $state<Ladefehler | null>(null);
  let flaeche: HTMLElement | undefined = $state();
  let blatt: HTMLElement | undefined = $state();
  let satz: HTMLElement | undefined = $state();
  let fluss: Textfluss | null = null;
  let stand = $state({ anteil: 0, amAnfang: true, amEnde: false });
  let trefferliste = $state.raw<HTMLElement[]>([]);
  let trefferNr = $state(-1);

  let gesamt = $derived(buch.page_count > 1 ? buch.page_count : Math.max(1, Math.ceil((inhalt?.length ?? 0) / ZEICHEN_JE_SEITE)));
  let seite = $derived(Math.max(1, Math.min(gesamt, Math.ceil(stand.anteil * gesamt) || 1)));

  async function lade() {
    fehler = null;
    try {
      inhalt = await (await anfrage(dateiUrl(buch.id))).text();
    } catch {
      fehler = await ladefehler(buch.id);
    }
  }

  /** Wird gerufen, sobald der Text auf dem Blatt steht */
  async function steht() {
    await tick();
    if (!flaeche || !blatt || !satz) return;
    const s = satz;
    sitzung.kapitel = sammleKapitel();
    zeichneMarkierungen(s, sitzung.markierungen);
    fluss ??= new Textfluss({ flaeche, blatt, satz }, art, bewegt);
    const ab = start.prozent ? start.prozent / 100 : start.seite ? (start.seite - 1) / gesamt : nenntStelle(start) ? 0 : (alt.scrollPct ?? 0) / 100;
    fluss.zuAnteil(ab);
    if (istMarkdown) void faerbeCode(s).then(() => kopierknoepfe(s));
    if (start.wort || start.stelle) zeigeTreffer(start.wort || start.stelle, ab);
  }

  function sammleKapitel(): Kapitel[] {
    if (!satz) return [];
    if (istMarkdown) return [...satz.querySelectorAll<HTMLElement>("h1, h2, h3, h4")].map((h) => ({ titel: h.textContent?.trim() || "Ohne Titel", tiefe: Number(h.tagName[1]) - 1, ziel: h }));
    return textkapitel((inhalt ?? "").split("\n")).map((k) => ({ titel: k.titel, tiefe: 0, ziel: k.anteil }));
  }

  function zeigeTreffer(wort: string, ab: number) {
    if (!satz || !fluss) return;
    trefferliste = zeichneTreffer(satz, wort);
    if (!trefferliste.length) return;
    const nr = ab > 0 ? trefferliste.findIndex((t) => fluss!.anteilVon(t, 0) >= ab - 0.002) : 0;
    zumTreffer(Math.max(0, nr));
  }

  function zumTreffer(nr: number) {
    trefferNr = (nr + trefferliste.length) % trefferliste.length;
    fluss?.zu(trefferliste[trefferNr]);
  }

  function trefferZu() {
    if (satz) zeichneTreffer(satz, "");
    trefferliste = [];
  }

  function bewegt() {
    if (!fluss) return;
    stand = { anteil: fluss.anteil, amAnfang: fluss.amAnfang, amEnde: fluss.amEnde };
    if (istMarkdown) sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => fluss!.erreicht(k.ziel as HTMLElement));
    else sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as number) <= stand.anteil + 0.002);
    merke();
  }

  function merke() {
    const farben = eigeneFarben ? { fgColor: w.fg, bgColor: w.bg } : {};
    const prozent = Math.round(stand.anteil * 1000) / 10;
    speicher.merke({ scrollPct: prozent, fontSize: w.groesse, fontFamily: w.schrift, lineHeight: w.zeilen, breite: w.breite, ...farben, blattTransparent: w.durchsichtig }, { percent: prozent > 0 ? prozent : undefined });
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

  // Anderer Rand: dieselbe Stelle bleibt
  $effect(() => {
    void [blattrand.wert, schale.vollbild];
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
    abschnittName: "",
    abschnitt: async () => "",
    zumKapitel: (k) => (k.ziel instanceof HTMLElement ? fluss?.zu(k.ziel) : fluss?.zuAnteil(k.ziel as number)),
    zurMarkierung: (m) => {
      const gezeichnet = satz?.querySelector<HTMLElement>(`mark[data-markierung="${m.id}"]`);
      if (gezeichnet) fluss?.zu(gezeichnet);
      else fluss?.zuAnteil((prozentVon(m.cfi_range) ?? 0) / 100);
    },
    zurStelle: (ort, cfi, p) => {
      const prozent = p || (prozentVon(cfi) ?? (Number(ort.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".")) || 0));
      const nr = Number(ort.match(/(\d+)/)?.[1]) || 0;
      if (!prozent && !nr) return false;
      fluss?.zuAnteil(prozent ? prozent / 100 : (nr - 1) / gesamt);
      return true;
    },
    zeichne: () => satz && zeichneMarkierungen(satz, sitzung.markierungen),
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
    return blaettergesten(f, { rahmen: () => f.getBoundingClientRect() }, { gilt: () => art === "blaettern", vor, zurueck, mitte: () => sitzung.tippeMitte(), belegt: () => sitzung.belegt() });
  });

  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    fluss?.zerstoere();
    sitzung.griffe = null;
  });

  void lade();
</script>

<svelte:window onkeydown={(e) => blaettertaste(e, art, tasten)} />

<Leserahmen {sitzung} {art} onart={(a) => leseart.blatt.setze(a)} grund={d.bg} tinte={d.fg} bereit={inhalt !== null} {onzurueck} onabwahl={abwahl} treffer={trefferliste.length ? trefferleiste : undefined}>
  {#if inhalt === null}
    <Ladehinweis {fehler} adresse={dateiUrl(buch.id)} name={buch.file_name || buch.title} onerneut={() => void lade()} />
  {:else}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="seiten lesetext textbuch rollen" tabindex="0" role="document" aria-label="Text" style:--lesebreite={BREITEN[d.breite].breite} bind:this={flaeche}>
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
    <Fussleiste anteil={stand.anteil} anAnfang={stand.amAnfang} amEnde={stand.amEnde} onzurueck={zurueck} onvor={vor} onanteil={(a) => fluss?.zuAnteil(a)}>
      <Seitenstand {seite} {gesamt} onseite={(nr) => fluss?.zuAnteil((nr - 1) / gesamt)} />
      <span class="stand zahl klein nur-breit">{Math.round(stand.anteil * 100)} %, {formatName(buch.file_format)}</span>
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet trefferleiste()}
  <Trefferleiste wort={start.wort || start.stelle} nr={trefferNr} gesamt={trefferliste.length} onspringe={zumTreffer} onschliessen={trefferZu} />
{/snippet}
