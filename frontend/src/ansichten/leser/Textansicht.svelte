<script lang="ts">
  // Seiten eines PDF als umfließender Text, mit Überschriften, Kästen und Abbildungen an ihrer Stelle
  import "../../stil/lesetext.css";
  import { onDestroy, tick, untrack } from "svelte";
  import { textBildUrl } from "../../lib/api/books";
  import { inhaltsbild } from "../../lib/inhaltsbild";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { blaettergesten } from "../../lib/leser/blaettergesten";
  import { blattrand } from "../../lib/leser/blattrand.svelte";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import { Textfluss } from "../../lib/leser/fluss/textfluss";
  import { Textseiten, type Baustein } from "../../lib/leser/pdf/textseiten.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { kannHervorheben, Rechteckschicht } from "../../lib/leser/hervorhebung";
  import { imBlick, Mitlauf, sichtVon } from "../../lib/leser/mitlauf";
  import { rechteckeVon } from "../../lib/leser/festbereich";
  import { zeichneMarkierungen, zeichneWortlaut } from "../../lib/leser/text/markierung";
  import type { Randeintrag } from "../../lib/leser/randmarken";
  import { absatzBei, vorgelesenIn } from "../../lib/leser/fokus";
  import { lesehilfen } from "../../lib/leser/lesehilfen.svelte";
  import type { Hilfeort } from "../../lib/leser/sitzung.svelte";
  import { nutzeSchrift } from "../../lib/leser/schriften";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Bildlupe from "./Bildlupe.svelte";
  import Codetaste from "./Codetaste.svelte";
  import type { Codestellenstand } from "../../lib/leser/codestellen.svelte";
  import type { Codestelle } from "../../lib/api/ausfuehren";
  import { ausfuehren } from "../../lib/stand/ausfuehren.svelte";

  interface Eigenschaften {
    sitzung: Lesesitzung;
    art: Leseart;
    startSeite: number;
    /** Wortlaut, der auf der Startseite gesucht wurde */
    fundstelle: string;
    grund: string;
    tinte: string;
    onstand: (stand: { seite: number; amAnfang: boolean; amEnde: boolean; innen: number }) => void;
    onoriginal: () => void;
    onmitte: () => void;
    belegt: (punkt: { x: number; y: number }) => boolean;
    /** Der Text hat sich geändert (nachgeladen, umgebrochen) */
    onbeschriftet: () => void;
    /** Codestellen mit Taste (BF-29); ohne Sandbox keine */
    codestellen?: Codestellenstand | null;
    oncode?: (s: Codestelle) => void;
    seitenname?: (nr: number) => string;
  }
  let { sitzung, art, startSeite, fundstelle, grund, tinte, onstand, onoriginal, onmitte, belegt, onbeschriftet, codestellen = null, oncode = () => {}, seitenname = String }: Eigenschaften = $props();

  let flaeche: HTMLElement | undefined = $state();
  let blatt: HTMLElement | undefined = $state();
  let satz: HTMLElement | undefined = $state();
  let lupe = $state<{ quelle: string; beschreibung: string } | null>(null);
  let fluss: Textfluss | null = null;
  let ersatzschicht: Rechteckschicht | undefined;
  let markiert = new Map<number, StaticRange>();
  let mitlauf: Mitlauf | null = null;
  let gemeldet = 0;
  let gesucht = untrack(() => fundstelle);

  const text = new Textseiten(untrack(() => sitzung.buch.id), async (tun) => {
    const umbau = async () => {
      tun();
      await tick();
      zeichne();
    };
    if (fluss) await fluss.halte(umbau);
    else await umbau();
  });

  // Nachladen, bevor man an den Rand des Geladenen kommt. Vorn von selbst nur beim Blättern: ein Schwung mit dem Finger
  // stockte sonst, dort gibt es die Taste.
  const VORRAT = 2;
  async function fuelleNach() {
    if (!fluss) return;
    const hinten = fluss.danach < VORRAT && text.mitHinten;
    const vorn = !hinten && art === "blaettern" && fluss.davor < VORRAT && text.mitVorn;
    if (hinten ? await text.unten() : vorn && (await text.oben())) bewegt();
  }

  const seiteVon = (k: Node | undefined) => Number((k?.nodeType === Node.ELEMENT_NODE ? (k as Element) : k?.parentElement)?.closest<HTMLElement>("[data-textseite]")?.dataset.textseite) || 0;
  const abschnitt = (nr: number) => satz?.querySelector<HTMLElement>(`[data-textseite="${nr}"]`) ?? null;

  function bewegt() {
    if (!fluss) return;
    const nr = seiteVon(fluss.halt()?.knoten) || text.erste;
    gemeldet = nr;
    const amAnfang = fluss.amAnfang && text.erste === 1;
    const amEnde = fluss.amEnde && text.letzte >= text.gesamt;
    // Wie weit man in den geladenen Seiten ist, für einen Balken, der bei jedem Schirm vorrückt
    const geladen = text.letzte - text.erste + 1;
    const innen = amEnde ? 1 : Math.min(0.999, Math.max(0, fluss.anteil * geladen - (nr - text.erste)));
    onstand({ seite: nr, amAnfang, amEnde, innen });
    ersatzschicht?.zeichne();
    sitzung.bewegt();
    void fuelleNach();
  }

  async function beginne(ab: number) {
    if (!(await text.neu(ab))) return;
    await tick();
    if (!flaeche || !blatt || !satz) return;
    if (!kannHervorheben()) ersatzschicht ??= new Rechteckschicht(blatt);
    const f = flaeche;
    mitlauf ??= new Mitlauf({ get stand() { return f.scrollTop; }, set stand(w) { f.scrollTop = w; }, get hoehe() { const s = sichtVon(f); return s.unten - s.oben; } }, f);
    fluss ??= new Textfluss({ flaeche, blatt, satz }, art, bewegt);
    fluss.neu();
    springe(ab);
  }

  function springe(nr: number) {
    const a = abschnitt(nr);
    if (!a || !fluss) return;
    const treffer = gesucht && nr === startSeite ? zeichneWortlaut(a, gesucht, ersatzschicht) : null;
    if (treffer) gesucht = "";
    gemeldet = nr;
    fluss.zu(treffer ?? a);
  }

  // Sprung von außen (Seitenfeld, Verzeichnis): steht die Seite schon da, nur hin, sonst neu laden
  $effect(() => {
    const ziel = startSeite;
    if (!satz) return;
    untrack(() => {
      if (ziel === gemeldet) return;
      if (abschnitt(ziel)) springe(ziel);
      else void beginne(ziel);
    });
  });

  $effect(() => {
    const neu = art;
    untrack(() => {
      fluss?.setzeArt(neu);
      void fuelleNach();
    });
  });

  $effect(() => nutzeSchrift(textansicht.familie));

  // Schrift, Zeilen, Rand: dieselbe Stelle bleibt
  $effect(() => {
    void [textansicht.groesse, textansicht.zeilen, textansicht.familie, blattrand.wert, schale.vollbild, lesehilfen.wirksam];
    untrack(() => void fluss?.halte(tick));
  });

  /** Einen Schirm weiter; am Rand des Geladenen erst nachholen */
  export async function vor() {
    if (fluss && !fluss.vor() && (await text.unten())) fluss.vor();
  }
  export async function zurueck() {
    if (fluss && !fluss.zurueck() && (await text.oben())) fluss.zurueck();
  }
  export function zeichne() {
    if (!satz) return;
    const seitenweise = sitzung.markierungen.filter((m) => m.cfi_range.startsWith("page:"));
    markiert = zeichneMarkierungen(satz, seitenweise, ersatzschicht, (m) => abschnitt(Number(m.cfi_range.slice(5))));
    onbeschriftet();
  }

  // Für das Vorlesen
  export const wurzel = (nr: number): HTMLElement | null => abschnitt(nr);
  export const ersatz = () => ersatzschicht;
  export const seiten = () => [gemeldet || startSeite];

  export async function zeige(nr: number, bereich: Range | null, sofort: boolean): Promise<void> {
    if (!fluss || !flaeche) return;
    if (!abschnitt(nr)) return void (await beginne(nr));
    if (!bereich) {
      if (seiteVon(fluss.halt()?.knoten) !== nr) springe(nr);
      return;
    }
    const a = { knoten: bereich.startContainer, versatz: bereich.startOffset };
    if (fluss.art === "blaettern") {
      if (!fluss.zeigt(a)) fluss.zu(a);
      return;
    }
    const r = bereich.getBoundingClientRect();
    const s = sichtVon(flaeche);
    mitlauf?.folge(r.top - s.oben, r.bottom - s.oben, sofort);
  }

  export function sichtbar(nr: number, bereich: Range | null): boolean {
    if (!fluss || !flaeche) return false;
    if (!bereich) return seiteVon(fluss.halt()?.knoten) === nr;
    if (fluss.art === "scrollen") return imBlick(bereich, sichtVon(flaeche));
    return fluss.zeigt({ knoten: bereich.startContainer, versatz: bereich.startOffset }) || fluss.zeigt({ knoten: bereich.endContainer, versatz: Math.max(0, bereich.endOffset - 1) });
  }

  // Für die Marken am Rand
  function sicht() {
    if (art === "scrollen" || !blatt) return sichtVon(flaeche!);
    const b = blatt.getBoundingClientRect();
    return { oben: b.top, unten: b.bottom, links: b.left, rechts: b.right };
  }

  export function lage(nr: number, e: Randeintrag): number | null {
    const a = abschnitt(nr);
    if (!a || !flaeche) return null;
    const s = sicht();
    const r = e.art === "Markierung" ? markiert.get((e.quelle as { id: number }).id) : null;
    if (r?.startContainer.isConnected && imBlick(r, s)) return rechteckeVon(r)[0]?.top ?? null;
    // Sonst der Anfang der Seite, wenn er auf dem Schirm steht
    for (const q of a.getClientRects()) if (q.right > s.links && q.left < s.rechts && q.bottom > s.oben && q.top < s.unten) return Math.max(q.top, s.oben);
    return null;
  }

  export const kante = (): number | null => blatt?.getBoundingClientRect().right ?? null;

  // Für die Lesehilfen
  export const hilfeort: Hilfeort = {
    blatt: () => blatt?.getBoundingClientRect() ?? null,
    zeilenhoehe: () => (blatt ? Number.parseFloat(getComputedStyle(blatt).lineHeight) || 26 : 26),
    absatzBei: (x, y) => (satz ? absatzBei(document, x, y, satz) : null),
    vorgelesen: () => vorgelesenIn(document, satz ?? null),
    mitAbsaetzen: true,
    rolle: (px) => {
      const vorher = flaeche!.scrollTop;
      flaeche!.scrollTop += px;
      return flaeche!.scrollTop !== vorher;
    },
    blaettere: () => {
      void vor();
      return !(fluss?.amEnde && text.letzte >= text.gesamt);
    },
    art: () => art,
  };

  export function hier(): { seite: number; wortlaut: string } {
    const h = fluss?.halt();
    const k = h?.knoten;
    return { seite: seiteVon(k) || gemeldet || startSeite, wortlaut: k?.nodeType === Node.TEXT_NODE ? (k as Text).data.slice(h!.versatz, h!.versatz + 60) : "" };
  }

  $effect(() => {
    if (!flaeche) return;
    const griffe = { gilt: () => art === "blaettern", vor, zurueck, mitte: onmitte, belegt };
    return blaettergesten(flaeche, { rahmen: () => flaeche!.getBoundingClientRect() }, griffe);
  });

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    const beschreibe = (b: Range) => {
      const nr = seiteVon(b.startContainer) || gemeldet;
      return { cfi: `page:${nr}`, ort: schreibweise.seite(nr) };
    };
    return beobachteAuswahl(f, beschreibe, (a) => nimmAuswahl(sitzung, a) && getSelection()?.removeAllRanges());
  });

  onDestroy(() => {
    fluss?.zerstoere();
    mitlauf?.zerstoere();
    ersatzschicht?.zerstoere();
  });

  // Die Bildunterschrift gleich nach einer Abbildung beschreibt sie in der Lupe
  const beschreibung = (liste: Baustein[], n: number) => (liste[n + 1]?.art === "unterschrift" ? liste[n + 1].text : "");
</script>

{#snippet abbildung(nr: number, b: Baustein, worte: string)}
  {@const quelle = textBildUrl(sitzung.buch.id, nr, b.bild!)}
  <button type="button" class="abbildung" aria-label="Abbildung vergrößern" onclick={() => (lupe = { quelle, beschreibung: worte })}>
    <img src={quelle} alt={worte} loading="lazy" use:inhaltsbild style:aspect-ratio={b.verhaeltnis ?? "auto"} style:--verhaeltnis={b.verhaeltnis ?? undefined} style:width={b.breite_em ? `${b.breite_em}em` : undefined} />
  </button>
{/snippet}

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div class="seiten lesetext textansicht rollen" lang="de" tabindex="0" role="document" aria-label="Text" bind:this={flaeche}>
  <article class="blatt" bind:this={blatt} style:--blattgrund={grund} style:--blatttinte={tinte} style:font-family={textansicht.familie} style:font-size="{(1.125 * textansicht.groesse) / 100}rem" style:line-height={textansicht.zeilen}>
    <div class="satz" bind:this={satz}>
      {#if text.mitVorn && art === "scrollen"}<div class="mitte frueher"><Knopf text="Frühere Seiten" symbol="arrow-up" klein laeuft={text.laedt} onclick={() => void text.oben()} /></div>{/if}
      {#if text.ohneText}
        <p>Diese Seiten sind Bilder ohne lesbaren Text, etwa eingescannt.</p>
        <div class="mitte"><Knopf text="Original" symbol="file-pdf" klein onclick={onoriginal} /></div>
      {/if}
      {#each text.seiten as s (s.nr)}
        <section data-textseite={s.nr}>
          <div class="seitenmarke">Seite {s.gedruckt || s.nr}</div>
          {#each s.bausteine as b, n (n)}
            {#if b.art === "ueberschrift"}<h2>{b.text}</h2>
            {:else if b.art === "unterschrift"}<p class="unterschrift">{b.text}</p>
            {:else if b.art === "bild"}{@render abbildung(s.nr, b, beschreibung(s.bausteine, n))}
            {:else if b.art === "kasten"}
              <aside class="kasten">
                {#if b.titel}<b>{b.titel}</b>{/if}
                {#each b.inhalt as t, j (j)}{#if t.art === "bild"}{@render abbildung(s.nr, t, "")}{:else}<p>{t.text}</p>{/if}{/each}
              </aside>
            {:else if b.art === "code"}
              <!-- Codestelle als Code statt als Bildausschnitt; den Titel und die Taste trägt der erste Teil, jeder weitere
                   die Marke der Fortsetzung (BF-29) -->
              {@const stelle = codestellen?.stelle(b.kennung ?? "") ?? null}
              <div class="codeteil" class:offen={!!stelle && ausfuehren.istOffen(sitzung.buch.id, stelle.kennung)} data-kennung={b.kennung} data-teil={b.teil}>
                {#if !b.teil && (b.titel || stelle)}
                  <div class="codekopf"><b class="codetitel">{b.titel}</b>{#if stelle}<Codetaste {stelle} fest onoeffne={() => oncode(stelle)} />{/if}</div>
                {:else if b.teil && stelle}
                  <div class="codekopf"><Codetaste {stelle} fest weiterVon={seitenname(stelle.teile[0].seite ?? s.nr)} onoeffne={() => oncode(stelle)} /></div>
                {/if}
                <pre><code>{(b.zeilen ?? []).join("\n")}</code></pre>
              </div>
            {:else}<p>{b.text}</p>{/if}
          {/each}
        </section>
      {/each}
      {#if text.fehler}<p>Der Text ließ sich nicht laden: {text.fehler}</p><div class="mitte"><Knopf text="Erneut versuchen" symbol="rotate-right" klein onclick={() => void (text.seiten.length ? text.unten() : beginne(startSeite))} /></div>{/if}
      {#if text.gesamt > 0 && text.letzte >= text.gesamt}<div class="mitte ende">Ende</div>{:else if text.laedt && !text.seiten.length}<div class="mitte ende">Lädt</div>{/if}
    </div>
  </article>
</div>

{#if lupe}<Bildlupe {...lupe} onschliessen={() => (lupe = null)} />{/if}

<style>
  .mitte {
    display: flex;
    justify-content: center;
    padding: 0.5rem 0;
  }
  .ende {
    font-size: 0.8em;
    opacity: 0.7;
  }
  .seitenmarke {
    font-size: 0.75em;
    opacity: 0.65;
    text-align: center;
    padding: 1.25em 0 0.5em;
  }
  .satz h2 {
    font-family: inherit;
    margin: 1em 0 0.5em;
  }
  .unterschrift {
    font-size: 0.85em;
    opacity: 0.8;
  }
  .kasten {
    margin: 1em 0;
    padding: 0.75em 1em;
    border-radius: var(--r2);
    border: 1px solid color-mix(in srgb, currentColor 30%, transparent);
    background: color-mix(in srgb, currentColor 6%, transparent);
  }
  .abbildung {
    display: block;
    margin: 1em auto;
    cursor: zoom-in;
  }
  /* Code wie im Text der Bücher (Markdown): Festbreite, dunkel hinterlegt; Zeilen und Einrückung bleiben, wie gedruckt,
     zu lange Zeilen rollen im Block */
  .codeteil {
    margin: 1em 0;
  }
  .codekopf {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.375rem;
  }
  .codekopf :global(.codetaste.fest) {
    height: 2.75rem;
    font-size: 0.875rem;
  }
  .codekopf :global(.codetaste.weiter) {
    margin-left: 0;
  }
  .codetitel {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font: 600 0.85em var(--schrift);
    hyphens: none;
  }
  /* Im Fenster offen: Ring um den Code wie die Streifen im Original */
  .codeteil.offen pre {
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--messing-flaeche) 75%, transparent);
  }
  .codeteil pre {
    margin: 0;
    padding: 0.875em 1em;
    border-radius: var(--r2);
    background: #14201e;
    color: #e8efe9;
    font: 400 0.88em/1.5 var(--codeschrift);
    white-space: pre;
    overflow-x: auto;
    hyphens: none;
    font-variant-ligatures: none;
    tab-size: 4;
  }
  .abbildung img {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 3px;
    background: #fff;
  }
  /* Geblättert passt jede Abbildung ganz auf einen Schirm, ohne weißen Rand daneben */
  :global(.schirmweise) .abbildung img {
    max-width: min(100%, calc((var(--satzhoehe) - 5em) * var(--verhaeltnis, 100)));
  }
</style>
