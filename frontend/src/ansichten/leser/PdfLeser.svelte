<script lang="ts">
  // PDF: Seiten als Bild mit wählbarem Text, oder als umfließender Text
  import { onDestroy, tick, untrack } from "svelte";
  import { dateiUrl, textSeiten, volltextSuche } from "../../lib/api/books";
  import { schreibtGerade } from "../../lib/flucht";
  import { beobachteAuswahl, nimmAuswahl } from "../../lib/leser/auswahl";
  import { papierOder, type Papier } from "../../lib/leser/darstellung";
  import { PdfAnzeige } from "../../lib/leser/pdf/anzeige";
  import { gedruckteSeite, ladePdf, seitentext, verzeichnis, type PdfBuch } from "../../lib/leser/pdf/dokument";
  import { leereEbene, zeichneFundstelle, zeichneMarkierungen } from "../../lib/leser/pdf/markierung";
  import { ansichtOder, einpassen, geblaettert, naechsteStufe, sichtbareSeiten, STUFEN, type Ansicht } from "../../lib/leser/pdf/zoom";
  import { Positionsspeicher } from "../../lib/leser/position";
  import type { Lesegriffe, Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { schreibweise } from "../../lib/leser/typen";
  import { wischen } from "../../lib/leser/wischen";
  import { gemerkt, type Leseziel } from "../../lib/leser/ziel";
  import { lesewerte, type Lesewerte } from "../../lib/lesestand";
  import { darstellung } from "../../lib/stand/darstellung.svelte";
  import { geraet } from "../../lib/stand/geraet.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Ladehinweis from "./Ladehinweis.svelte";
  import Leserahmen from "./Leserahmen.svelte";
  import PdfDarstellung from "./PdfDarstellung.svelte";
  import Fussleiste from "./Fussleiste.svelte";
  import Seitenstand from "./Seitenstand.svelte";
  import Textansicht from "./Textansicht.svelte";

  let { buch, ziel, sitzung, onzurueck }: { buch: BuchEinzeln; ziel: Leseziel; sitzung: Lesesitzung; onzurueck: () => void } = $props();

  // Das Gerät zählt beim Öffnen: Telefon und Rechner merken Ansicht und Zoom getrennt
  const telefon = geraet.telefon;
  const alt: Lesewerte = untrack(() => gemerkt(ziel, lesewerte(buch.reading_position)));
  const meine = telefon ? (alt.telefon ?? {}) : alt;
  const start = untrack(() => ziel);
  const speicher = new Positionsspeicher(untrack(() => buch.id), "pdf");

  let flaeche: HTMLElement | undefined = $state();
  let pdf = $state.raw<PdfBuch | null>(null);
  let fehler = $state("");
  let seite = $state(start.seite || alt.page || 1);
  let ansicht = $state<Ansicht>(ansichtOder(start.ansicht || meine.ansicht, telefon ? "breite" : "scroll"));
  let mass = $state((start.zoom || meine.zoom || 100) / 100);
  let papierWahl = $state(start.papier || alt.papier || "");
  let nurText = $state(telefon ? textansicht.an : (start.ansicht || alt.ansicht) === "text");
  // Nur was von Hand gewählt wurde, wird gemerkt: Telefon und Rechner überschreiben einander nicht
  let ansichtGewaehlt = $state(false);
  let fundstelle = $state(start.stelle || start.wort);
  let fundseite = $state(start.seite);
  let gerolltZurFundstelle = false;
  let gedruckt = $state("");
  let anzeige: PdfAnzeige | null = null;

  let papier = $derived<Papier>(papierOder(papierWahl, darstellung.dunkel));
  let gesamt = $derived(pdf?.seiten ?? buch.page_count);
  let blaettert = $derived(geblaettert(ansicht));
  let bogen = $derived(blaettert && pdf ? sichtbareSeiten(ansicht, seite, pdf.seiten) : []);

  async function lade() {
    fehler = "";
    try {
      const geladen = await ladePdf(buch.id);
      if (!start.seite && start.wort) await sucheSeite();
      seite = Math.min(Math.max(1, seite), geladen.seiten);
      pdf = geladen;
      await tick();
      baue();
      sitzung.kapitel = await verzeichnis(geladen.doc);
    } catch (e) {
      fehler = e instanceof Error ? e.message : "Das PDF ließ sich nicht laden";
    }
  }

  // ?q ohne Seite: auf die erste Seite, die den Begriff enthält
  async function sucheSeite() {
    const wort = start.wort.replace(/"/g, "");
    const treffer = await volltextSuche(buch.id, wort, { limit: 1 }).catch(() => null);
    const nr = treffer?.treffer[0]?.seite;
    if (nr) [seite, fundseite] = [nr, nr];
  }

  function baue() {
    if (!pdf || !flaeche) return;
    anzeige = new PdfAnzeige(pdf, flaeche, { beiSeite: gelesen, gezeichnet: beschrifte });
    rechne();
  }

  function freieFlaeche() {
    const f = flaeche!;
    const s = getComputedStyle(f);
    return { breite: f.clientWidth - Number.parseFloat(s.paddingLeft) - Number.parseFloat(s.paddingRight), hoehe: f.clientHeight - Number.parseFloat(s.paddingTop) - Number.parseFloat(s.paddingBottom) };
  }

  async function rechne() {
    if (!pdf || !flaeche || !anzeige || nurText) return;
    mass = einpassen(ansicht, pdf.mass, freieFlaeche()) ?? mass;
    Object.assign(anzeige, { mass, ansicht, seite });
    await tick();
    await anzeige.neu();
  }

  function beschrifte(nr: number, ebene: HTMLElement) {
    zeichneMarkierungen(ebene, nr, sitzung.markierungen);
    if (!fundstelle || nr !== fundseite) return;
    const erstes = zeichneFundstelle(ebene, fundstelle);
    if (erstes && !gerolltZurFundstelle && !blaettert) {
      gerolltZurFundstelle = true;
      erstes.scrollIntoView({ block: "center" });
    }
  }

  function gelesen(nr: number) {
    seite = nr;
    merke();
  }

  function merke() {
    const meinStand = { ansicht: telefon ? ansicht : nurText ? "text" : ansicht, zoom: ansicht === "scroll" ? Math.round(mass * 100) : meine.zoom };
    const werte: Lesewerte = { ...alt, page: seite, ...(papierWahl ? { papier: papierWahl } : {}) };
    if (telefon && ansichtGewaehlt) werte.telefon = meinStand;
    if (!telefon) Object.assign(werte, ansichtGewaehlt || alt.ansicht ? meinStand : {});
    Object.assign(alt, werte);
    const inAdresse = ansichtGewaehlt && !telefon;
    speicher.merke(werte, { page: seite > 1 ? seite : undefined, ansicht: inAdresse && ansicht !== "scroll" ? ansicht : undefined, zoom: inAdresse && ansicht === "scroll" && mass !== 1 ? Math.round(mass * 100) : undefined, papier: papierWahl || undefined });
  }

  function geheZu(nr: number) {
    if (nr < 1 || nr > gesamt) return;
    seite = nr;
    if (anzeige && !nurText) {
      anzeige.seite = nr;
      if (blaettert) void tick().then(() => anzeige?.neu());
      else anzeige.zeige(nr);
    }
    merke();
  }

  const schritt = $derived(ansicht === "doppel" && !nurText ? 2 : 1);
  const vor = () => geheZu(Math.min(gesamt, seite + schritt));
  const zurueck = () => geheZu(Math.max(1, seite - schritt));

  function setzeAnsicht(neu: Ansicht | "text") {
    ansichtGewaehlt = true;
    nurText = neu === "text";
    if (telefon) textansicht.an = nurText;
    if (neu !== "text") ansicht = neu;
    void tick().then(rechne);
    merke();
  }

  function setzeZoom(neu: number) {
    ansichtGewaehlt = true;
    // Am Telefon rastet die Seitenbreite ein, statt darunter weiterzugehen
    const passend = pdf && flaeche ? einpassen("breite", pdf.mass, freieFlaeche()) : null;
    if (telefon && passend !== null && neu <= passend) return setzeAnsicht("breite");
    ansicht = "scroll";
    mass = neu;
    void rechne();
    merke();
  }

  const zoome = (richtung: 1 | -1) => setzeZoom(naechsteStufe(mass, richtung));

  function taste(e: KeyboardEvent) {
    if (schreibtGerade(e) || e.metaKey || e.ctrlKey || e.altKey || document.querySelector("dialog[open]")) return;
    const griff: Record<string, () => void> = { "+": () => zoome(1), "=": () => zoome(1), "-": () => zoome(-1), ArrowRight: vor, PageDown: vor, ArrowLeft: zurueck, PageUp: zurueck, Home: () => geheZu(1), End: () => geheZu(gesamt) };
    const tun = griff[e.key];
    if (!tun || (nurText && "+=-".includes(e.key))) return;
    e.preventDefault();
    tun();
  }

  function zeichneMarken() {
    anzeige?.zeichneErneut((nr, ebene) => {
      leereEbene(ebene);
      beschrifte(nr, ebene);
    });
  }

  const griffe: Lesegriffe = {
    abschnittName: "Seite",
    abschnitt: async () => (pdf ? seitentext(pdf.doc, seite) : ""),
    zumKapitel: (k) => geheZu(k.ziel as number),
    zurMarkierung: (m) => geheZu(Number(m.cfi_range.match(/^page:(\d+)/)?.[1] ?? seite)),
    zurStelle: (ort, cfi) => {
      const nr = Number(cfi.match(/^page:(\d+)/)?.[1] ?? ort.match(/\d+/)?.[0] ?? 0);
      if (nr) geheZu(nr);
      return nr > 0;
    },
    zeichne: zeichneMarken,
    hier: () => ({ ort: schreibweise.seite(seite), prozent: gesamt ? (seite / gesamt) * 100 : 0, cfi: `page:${seite}` }),
  };

  untrack(() => (sitzung.griffe = griffe));

  const abwahl = () => getSelection()?.removeAllRanges();

  $effect(() => {
    const f = flaeche;
    if (!f || !pdf) return;
    const seiteVon = (bereich: Range) => Number((bereich.startContainer.parentElement?.closest("[data-seite]") as HTMLElement | null)?.dataset.seite) || seite;
    return beobachteAuswahl(f, (b) => ({ cfi: `page:${seiteVon(b)}`, ort: schreibweise.seite(seiteVon(b)) }), (a) => nimmAuswahl(sitzung, a) && abwahl());
  });

  // Blättern mit dem Finger, wo nicht fortlaufend gerollt wird
  $effect(() => {
    if (flaeche && ansicht !== "scroll" && !nurText) return wischen(flaeche, { links: vor, rechts: zurueck });
  });

  // Die Größe der Fläche ändert sich: eingepasste Ansichten neu rechnen
  $effect(() => {
    const f = flaeche;
    if (!f || !pdf) return;
    let zuvor = f.clientWidth + f.clientHeight;
    const beobachter = new ResizeObserver(() => {
      const jetzt = f.clientWidth + f.clientHeight;
      if (jetzt === zuvor || f.clientWidth === 0) return;
      zuvor = jetzt;
      if (ansicht !== "scroll") void rechne();
    });
    beobachter.observe(f);
    return () => beobachter.disconnect();
  });

  // Die Fundstelle ist ein Hinweis beim Ankommen, keine Markierung: weg, sobald man weiterliest
  $effect(() => {
    if (!fundstelle || Math.abs(seite - fundseite) <= 1) return;
    fundstelle = "";
    untrack(zeichneMarken);
  });

  // Kapitel, in dem man gerade ist
  $effect(() => {
    sitzung.kapitelJetzt = sitzung.kapitel.findLastIndex((k) => (k.ziel as number) <= seite);
  });

  // Gedruckte Seite: aus der Datei, sonst fragt der Leser nach kurzer Ruhe den Server
  $effect(() => {
    const nr = seite;
    const ausDatei = pdf ? gedruckteSeite(pdf, nr) : "";
    gedruckt = ausDatei;
    if (ausDatei || pdf?.beschriftung) return;
    const uhr = setTimeout(async () => {
      const antwort = await textSeiten(buch.id, nr, 1).catch(() => null);
      const wert = antwort?.seiten?.[0]?.gedruckt ?? "";
      if (nr === seite && wert && wert !== String(nr)) gedruckt = wert;
    }, 900);
    return () => clearTimeout(uhr);
  });

  const aufraeumen = speicher.starte();
  onDestroy(() => {
    aufraeumen();
    anzeige?.zerstoere();
    void pdf?.doc.loadingTask.destroy();
    sitzung.griffe = null;
  });

  void lade();
</script>

<svelte:window onkeydown={taste} />

<Leserahmen {sitzung} {papier} bereit={!!pdf} {onzurueck} onabwahl={abwahl}>
  {#if !pdf}
    <Ladehinweis {fehler} adresse={dateiUrl(buch.id)} name={buch.file_name || buch.title} onerneut={() => void lade()} />
  {:else}
    {#if nurText}
      <Textansicht {buch} startSeite={seite} onseite={gelesen} onoriginal={() => setzeAnsicht(ansicht)} />
    {/if}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div class="seiten pdf rollen" class:blaettert class:verborgen={nurText} tabindex="0" role="document" aria-label="Seiten" bind:this={flaeche} onscroll={() => anzeige?.gerollt()}>
      {#if blaettert}
        <div class="bogen">{#each bogen as nr (nr)}<div class="pdfseite" data-seite={nr}><span class="nummer">{nr}</span></div>{/each}</div>
      {:else}
        {#each { length: pdf.seiten } as _, n (n)}<div class="pdfseite" data-seite={n + 1}><span class="nummer">{n + 1}</span></div>{/each}
      {/if}
    </div>
  {/if}

  {#snippet darstellung()}
    <PdfDarstellung {ansicht} {nurText} {mass} {papier} stufen={STUFEN} onansicht={setzeAnsicht} onzoom={zoome} onoriginalgroesse={() => setzeZoom(1)} onpapier={(p) => { papierWahl = p; merke(); }} />
  {/snippet}

  {#snippet fuss()}
    <Fussleiste anteil={gesamt > 1 ? (seite - 1) / (gesamt - 1) : 0} anAnfang={seite <= 1} amEnde={seite >= gesamt} onzurueck={zurueck} onvor={vor} onanteil={(a) => geheZu(Math.round(1 + a * (gesamt - 1)))}>
      <Seitenstand {seite} {gesamt} {gedruckt} onseite={geheZu} />
    </Fussleiste>
  {/snippet}
</Leserahmen>
