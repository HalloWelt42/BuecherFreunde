<script lang="ts">
  // Text und Markdown: ein langes Blatt zum Rollen
  import "../../stil/lesetext.css";
  import { onDestroy, tick, untrack } from "svelte";
  import { dateiUrl } from "../../lib/api/books";
  import { anfrage } from "../../lib/api/client";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { GROESSE, istDunkel, oderVorgabe, vorgabeThema, ZEILEN } from "../../lib/leser/darstellung";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { faerbeCode, kopierknoepfe } from "../../lib/leser/text/codefarben";
  import { prozentVon, textkapitel, zeichneMarkierungen, zeichneTreffer } from "../../lib/leser/text/markierung";
  import { schreibweise, type Kapitel } from "../../lib/leser/typen";
  import { gemerkt, nenntStelle, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung as app } from "../../lib/stand/darstellung.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Fussleiste from "./Fussleiste.svelte";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import Markdown from "./Markdown.svelte";
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

  let inhalt = $state<string | null>(null);
  let fehler = $state("");
  let flaeche: HTMLElement | undefined = $state();
  let blatt: HTMLElement | undefined = $state();
  let anteil = $state(0);
  let trefferliste = $state.raw<HTMLElement[]>([]);
  let trefferNr = $state(-1);

  let gesamt = $derived(buch.page_count > 1 ? buch.page_count : Math.max(1, Math.ceil((inhalt?.length ?? 0) / ZEICHEN_JE_SEITE)));
  let seite = $derived(Math.max(1, Math.min(gesamt, Math.ceil(anteil * gesamt) || 1)));

  async function lade() {
    fehler = "";
    try {
      inhalt = await (await anfrage(dateiUrl(buch.id))).text();
    } catch (e) {
      fehler = e instanceof Error ? e.message : "Der Text ließ sich nicht laden";
    }
  }

  /** Wird gerufen, sobald der Text auf dem Blatt steht */
  async function steht() {
    await tick();
    if (!blatt || !flaeche) return;
    if (istMarkdown) {
      void faerbeCode(blatt).then(() => blatt && kopierknoepfe(blatt));
    }
    sitzung.kapitel = sammleKapitel();
    zeichneMarkierungen(blatt, sitzung.markierungen);
    const ab = start.prozent ? start.prozent / 100 : start.seite ? (start.seite - 1) / gesamt : nenntStelle(start) ? 0 : (alt.scrollPct ?? 0) / 100;
    requestAnimationFrame(() => {
      rolle(ab);
      if (start.wort || start.stelle) zeigeTreffer(start.wort || start.stelle, ab);
    });
  }

  function gesetzt(_knoten: HTMLElement) {
    void steht();
  }

  function sammleKapitel(): Kapitel[] {
    if (!blatt) return [];
    if (istMarkdown) return [...blatt.querySelectorAll<HTMLElement>("h1, h2, h3, h4")].map((h) => ({ titel: h.textContent?.trim() || "Ohne Titel", tiefe: Number(h.tagName[1]) - 1, ziel: h }));
    const zeilen = (inhalt ?? "").split("\n");
    return textkapitel(zeilen).map((k) => ({ titel: k.titel, tiefe: 0, ziel: k.zeile / zeilen.length }));
  }

  const spielraum = () => (flaeche ? flaeche.scrollHeight - flaeche.clientHeight : 0);

  function rolle(neu: number) {
    if (flaeche) flaeche.scrollTop = Math.max(0, Math.min(1, neu)) * spielraum();
  }

  function zuElement(e: HTMLElement) {
    if (flaeche) flaeche.scrollTop += e.getBoundingClientRect().top - flaeche.getBoundingClientRect().top - 80;
  }

  function zeigeTreffer(wort: string, ab: number) {
    if (!blatt || !flaeche) return;
    trefferliste = zeichneTreffer(blatt, wort);
    if (!trefferliste.length) return;
    const grenze = ab * spielraum();
    const nr = trefferliste.findIndex((t) => t.getBoundingClientRect().top - flaeche!.getBoundingClientRect().top + flaeche!.scrollTop >= grenze);
    zumTreffer(ab > 0 ? Math.max(0, nr) : 0);
  }

  function zumTreffer(nr: number) {
    trefferNr = (nr + trefferliste.length) % trefferliste.length;
    zuElement(trefferliste[trefferNr]);
  }

  function trefferZu() {
    if (blatt) zeichneTreffer(blatt, "");
    trefferliste = [];
  }

  function gerollt() {
    const s = spielraum();
    const neu = s > 0 ? flaeche!.scrollTop / s : 0;
    if (Math.abs(neu - anteil) < 0.0005) return;
    anteil = neu;
    if (istMarkdown) sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as HTMLElement).getBoundingClientRect().top < flaeche!.getBoundingClientRect().top + 120);
    else sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as number) <= anteil + 0.002);
    merke();
  }

  function merke() {
    const farben = eigeneFarben ? { fgColor: w.fg, bgColor: w.bg } : {};
    const prozent = Math.round(anteil * 1000) / 10;
    speicher.merke({ scrollPct: prozent, fontSize: w.groesse, fontFamily: w.schrift, lineHeight: w.zeilen, breite: w.breite, ...farben, blattTransparent: w.durchsichtig }, { percent: prozent > 0 ? prozent : undefined });
  }

  function setze(neu: Partial<Textdarstellung>) {
    if (neu.fg || neu.bg) {
      Object.assign(w, { fg: d.fg, bg: d.bg });
      eigeneFarben = true;
    }
    const halte = anteil;
    Object.assign(w, neu);
    // Größe und Breite ändern die Höhe des Textes: dieselbe Stelle bleibt oben
    void tick().then(() => rolle(halte));
    merke();
  }

  const blaettere = (richtung: 1 | -1) => flaeche?.scrollBy({ top: richtung * (flaeche.clientHeight - 160) });
  const abwahl = () => getSelection()?.removeAllRanges();

  function anteilVon(bereich: Range): number {
    const s = flaeche!.scrollHeight;
    return Math.min(1, Math.max(0, (bereich.getBoundingClientRect().top - flaeche!.getBoundingClientRect().top + flaeche!.scrollTop) / s));
  }

  const griffe: Lesegriffe = {
    abschnittName: "",
    abschnitt: async () => "",
    zumKapitel: (k) => (k.ziel instanceof HTMLElement ? zuElement(k.ziel) : rolle(k.ziel as number)),
    zurMarkierung: (m) => {
      const gezeichnet = blatt?.querySelector<HTMLElement>(`mark[data-markierung="${m.id}"]`);
      if (gezeichnet) zuElement(gezeichnet);
      else rolle((prozentVon(m.cfi_range) ?? 0) / 100);
    },
    zurStelle: (ort, cfi, p) => {
      const prozent = p || (prozentVon(cfi) ?? (Number(ort.match(/([\d.,]+)\s*%/)?.[1]?.replace(",", ".")) || 0));
      const nr = Number(ort.match(/(\d+)/)?.[1]) || 0;
      if (!prozent && !nr) return false;
      rolle(prozent ? prozent / 100 : (nr - 1) / gesamt);
      return true;
    },
    zeichne: () => blatt && zeichneMarkierungen(blatt, sitzung.markierungen),
    hier: () => ({ ort: schreibweise.seite(seite), prozent: Math.round(anteil * 1000) / 10, cfi: `percent:${(anteil * 100).toFixed(1)}` }),
  };
  untrack(() => (sitzung.griffe = griffe));

  $effect(() => {
    const f = flaeche;
    if (!f || inhalt === null) return;
    const beschreibe = (b: Range) => ({ cfi: `percent:${(anteilVon(b) * 100).toFixed(1)}`, ort: schreibweise.seite(Math.max(1, Math.ceil(anteilVon(b) * gesamt))) });
    return beobachteAuswahl(f, beschreibe, (a) => nimmAuswahl(sitzung, a) && abwahl());
  });

  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    sitzung.griffe = null;
  });

  void lade();
</script>

<Leserahmen {sitzung} bereit={inhalt !== null} {onzurueck} onabwahl={abwahl} treffer={trefferliste.length ? trefferleiste : undefined}>
  {#if inhalt === null}
    <Ladehinweis {fehler} adresse={dateiUrl(buch.id)} name={buch.file_name || buch.title} onerneut={() => void lade()} />
  {:else}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="seiten textbuch rollen" tabindex="0" role="document" aria-label="Text" style:--lesebreite={BREITEN[d.breite].breite} bind:this={flaeche} onscroll={gerollt}>
      <article class="blatt" class:ohne-grund={d.durchsichtig} class:dunkel={istDunkel(d.bg)} class:markdown={istMarkdown} lang={buch.language || "de"} bind:this={blatt}
        style:--blattgrund={d.durchsichtig ? "transparent" : d.bg} style:--blatttinte={d.fg} style:--lesegroesse="{1.125 * d.groesse / 100}rem" style:font-family={d.schrift || undefined} style:line-height={d.zeilen}>
        {#if istMarkdown}<Markdown quelle={inhalt} onsteht={steht} />{:else}<pre class="schlichttext" use:gesetzt>{inhalt}</pre>{/if}
      </article>
    </div>
  {/if}

  {#snippet darstellung()}<TextDarstellung {d} onwahl={setze} />{/snippet}

  {#snippet fuss()}
    <Fussleiste {anteil} anAnfang={anteil <= 0} amEnde={anteil >= 0.999} onzurueck={() => blaettere(-1)} onvor={() => blaettere(1)} onanteil={rolle}>
      <Seitenstand {seite} {gesamt} onseite={(nr) => rolle((nr - 1) / gesamt)} />
      <span class="stand zahl klein nur-breit">{Math.round(anteil * 100)} %</span>
    </Fussleiste>
  {/snippet}
</Leserahmen>

{#snippet trefferleiste()}
  <Trefferleiste wort={start.wort || start.stelle} nr={trefferNr} gesamt={trefferliste.length} onspringe={zumTreffer} onschliessen={trefferZu} />
{/snippet}
