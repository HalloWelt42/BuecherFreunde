<script>
  import { holeBuch, coverUrl, aktualisiereBuch, aehnlicheBuecher, volltextSuche } from "../lib/api/books.js";
  import { post, get as apiGet, getToken } from "../lib/api/client.js";
  import { ladeSammlungen, buchZuordnen, buchAusSammlung } from "../lib/api/collections.js";
  import { ladeKategorien, ordneBuchZu, entferneBuch as entferneKategorieBuch } from "../lib/api/categories.js";
  import { toggleFavorit, toggleZumLesen, toggleGelesen, setzeBewertung } from "../lib/api/user-data.js";
  import { sucheMetadaten, uebernehmMetadaten, ladeVolltext } from "../lib/api/metadata.js";
  import { notifyBooksChanged } from "../lib/stores/processes.svelte.js";
  import { navigate } from "../lib/router.svelte.js";
  import { ui } from "../lib/stores/ui.svelte.js";
  import RatingStars from "../lib/components/ui/RatingStars.svelte";
  import BookMeta from "../lib/components/book/BookMeta.svelte";
  import AiCategorizeDialog from "../lib/components/book/AiCategorizeDialog.svelte";
  import NoteList from "../lib/components/notes/NoteList.svelte";
  import { highlightsFuerBuch, loescheHighlight, aktualisiereHighlight } from "../lib/api/highlights.js";

  let { params } = $props();

  let book = $state(null);
  let laden = $state(true);
  let fehler = $state(null);
  let coverError = $state(false);
  let aiDialogOpen = $state(false);
  let kategorienAlle = $state(false);

  // Editiermodus
  let editMode = $state(false);
  let editData = $state({});
  let editSpeichern = $state(false);
  let sammlungen = $state([]);

  // ISBN-Scan
  let isbnScanLaden = $state(false);
  let isbnScanErgebnis = $state(null);

  // Cover neu extrahieren
  let coverNeuLaden = $state(false);

  // Buch-Volltextsuche
  let buchSucheOffen = $state(false);
  let buchSuchbegriff = $state("");
  let buchSuchTreffer = $state([]);
  let buchSuchGesamt = $state(0);
  let buchSuchLaden = $state(false);
  let buchSuchTimer = $state(null);
  let suchGanzesWort = $state(false);
  let suchGrossKlein = $state(false);
  let suchRegex = $state(false);

  // Markierungen (Highlights mit optionalen Labels)
  let markierungen = $state([]);
  let markierungOffen = $state({});

  // Kategorien bearbeiten
  let katEditMode = $state(false);
  let katSuche = $state("");
  let katAlleKategorien = $state([]);
  let katSuchTimer = $state(null);

  let katGefiltert = $derived(() => {
    if (!katSuche.trim()) return [];
    const q = katSuche.toLowerCase().trim();
    const buchKatIds = new Set((book?.categories || []).map(c => c.id));
    return katAlleKategorien
      .filter(c => !buchKatIds.has(c.id) && c.name.toLowerCase().includes(q))
      .slice(0, 10);
  });

  async function katEditStarten() {
    try {
      katAlleKategorien = await ladeKategorien();
    } catch { katAlleKategorien = []; }
    katSuche = "";
    katEditMode = true;
  }

  function katEditBeenden() {
    katEditMode = false;
    katSuche = "";
  }

  async function kategorieEntfernen(catId) {
    try {
      await entferneKategorieBuch(catId, book.id);
      await ladeBuch(book.id);
    } catch (e) {
      fehler = e.message || "Fehler beim Entfernen der Kategorie";
    }
  }

  async function kategorieHinzufuegen(catId) {
    try {
      await ordneBuchZu(catId, book.id);
      katSuche = "";
      await ladeBuch(book.id);
    } catch (e) {
      fehler = e.message || "Fehler beim Hinzufügen der Kategorie";
    }
  }

  // Aehnliche Buecher
  let aehnliche = $state({ vom_autor: [], in_kategorie: [] });

  async function coverNeuExtrahieren() {
    if (coverNeuLaden || !book) return;
    coverNeuLaden = true;
    try {
      await post(`/api/books/${book.id}/cover/neu-extrahieren`);
      coverError = false;
      await ladeBuch(book.id);
    } catch (e) {
      metaFehler = e.message || "Cover-Extraktion fehlgeschlagen";
    } finally {
      coverNeuLaden = false;
    }
  }

  function onBuchSuche(e) {
    const val = e.target.value;
    buchSuchbegriff = val;
    if (buchSuchTimer) clearTimeout(buchSuchTimer);
    if (!val || val.length < 2) {
      buchSuchTreffer = [];
      buchSuchGesamt = 0;
      return;
    }
    buchSuchTimer = setTimeout(() => starteSuche(val), 400);
  }

  async function starteSuche(val) {
    if (!val || val.length < 2) return;
    buchSuchLaden = true;
    try {
      const res = await volltextSuche(book.id, val, {
        ganzes_wort: suchGanzesWort,
        gross_klein: suchGrossKlein,
        regex: suchRegex,
      });
      buchSuchTreffer = res.treffer || [];
      buchSuchGesamt = res.gesamt || buchSuchTreffer.length;
    } catch {
      buchSuchTreffer = [];
      buchSuchGesamt = 0;
    } finally {
      buchSuchLaden = false;
    }
  }

  function toggleSuchFilter(filter) {
    if (filter === "wort") suchGanzesWort = !suchGanzesWort;
    else if (filter === "case") suchGrossKlein = !suchGrossKlein;
    else if (filter === "regex") suchRegex = !suchRegex;
    if (buchSuchbegriff.length >= 2) starteSuche(buchSuchbegriff);
  }

  async function startEdit() {
    editData = {
      title: book.title || "",
      author: book.author || "",
      isbn: book.isbn || "",
      publisher: book.publisher || "",
      year: book.year || "",
      language: book.language || "",
      description: book.description || "",
      page_count: book.page_count || "",
      typ: book.typ || "",
      sammlung_id: book.sammlung_id || null,
      band_nummer: book.band_nummer || "",
    };
    try { sammlungen = await ladeSammlungen(); } catch { sammlungen = []; }
    editMode = true;
  }

  function cancelEdit() {
    editMode = false;
    editData = {};
  }

  async function saveEdit() {
    if (editSpeichern) return;
    editSpeichern = true;
    try {
      const daten = {};
      for (const [key, val] of Object.entries(editData)) {
        if (key === "sammlung_id") continue; // separat behandeln
        if (key === "band_nummer") continue; // separat behandeln
        if (key === "year" || key === "page_count") {
          const num = parseInt(val) || null;
          if (num !== (book[key] || null)) daten[key] = num;
        } else {
          if (val !== (book[key] || "")) daten[key] = val;
        }
      }

      // Sammlung separat via Collections-API
      const neueSammlung = editData.sammlung_id ? Number(editData.sammlung_id) : null;
      const alteSammlung = book.sammlung_id || null;
      if (neueSammlung !== alteSammlung || editData.band_nummer !== (book.band_nummer || "")) {
        if (neueSammlung) {
          await buchZuordnen(neueSammlung, book.id, editData.band_nummer || "");
        } else if (alteSammlung) {
          await buchAusSammlung(alteSammlung, book.id);
        }
      }

      if (Object.keys(daten).length > 0) {
        await aktualisiereBuch(book.id, daten);
      }
      await ladeBuch(book.id);
      editMode = false;
      editData = {};
    } catch (e) {
      fehler = e.message || "Fehler beim Speichern";
    } finally {
      editSpeichern = false;
    }
  }

  async function isbnScannen() {
    if (isbnScanLaden || !book) return;
    isbnScanLaden = true;
    isbnScanErgebnis = null;
    try {
      isbnScanErgebnis = await post(`/api/books/${book.id}/isbn-scan`);
    } catch (e) {
      fehler = e.message || "ISBN-Scan fehlgeschlagen";
    } finally {
      isbnScanLaden = false;
    }
  }

  function isbnUebernehmen(isbn) {
    if (editMode) {
      editData.isbn = isbn;
    }
    isbnScanErgebnis = null;
  }

  // Metadaten-Anreicherung
  let metaLaden = $state(false);
  let metaSchritt = $state("");
  let metaVorschlag = $state(null);
  let metaAktuell = $state(null);
  let metaQuelle = $state("");
  let metaFehler = $state("");
  let metaAuswahl = $state({});

  // Volltext als Beschreibungsquelle
  let volltextOffen = $state(false);
  let volltextInhalt = $state("");
  let volltextLaden = $state(false);
  let volltextVon = $state(1);
  let volltextBis = $state(5);
  let volltextSeitenGesamt = $state(0);

  async function volltextLadenAktion() {
    if (volltextLaden || !book) return;
    volltextLaden = true;
    try {
      const result = await ladeVolltext(book.id, volltextVon, volltextBis);
      volltextInhalt = result.volltext || "";
      volltextSeitenGesamt = result.seiten_gesamt || 0;
      volltextVon = result.seite_von || 1;
      volltextBis = result.seite_bis || 5;
    } catch {
      volltextInhalt = "";
    } finally {
      volltextLaden = false;
    }
  }

  function volltextUebernehmen(text) {
    if (!metaVorschlag) return;
    metaVorschlag.beschreibung = text;
    metaAuswahl.beschreibung = true;
    volltextOffen = false;
  }

  async function volltextDirektUebernehmen() {
    if (!volltextInhalt || !book) return;
    try {
      await uebernehmMetadaten(book.id, { beschreibung: volltextInhalt });
      volltextOffen = false;
      volltextInhalt = "";
      await ladeBuch(book.id);
    } catch (e) {
      metaFehler = e.message || "Fehler beim Speichern";
    }
  }

  // Alle Rohdaten anzeigen
  let rawOffen = $state(false);

  // Einzelne Raw-Listen als Kategorien uebernehmen
  let rawKatAuswahl = $state({});

  const vergleichsFelder = [
    { key: "titel", label: "Titel" },
    { key: "autor", label: "Autor" },
    { key: "verlag", label: "Verlag" },
    { key: "jahr", label: "Jahr" },
    { key: "seiten", label: "Seiten" },
    { key: "isbn", label: "ISBN" },
    { key: "sprache", label: "Sprache" },
    { key: "beschreibung", label: "Beschreibung" },
  ];

  function metaInitAuswahl(vorschlag) {
    const auswahl = {};
    for (const feld of vergleichsFelder) {
      const neu = vorschlag[feld.key] ?? "";
      if (neu) {
        auswahl[feld.key] = true;
      }
    }
    if (vorschlag.cover_url) auswahl.cover = true;
    if (vorschlag.kategorien?.length) auswahl.kategorien = true;
    return auswahl;
  }

  let metaHatAuswahl = $derived(
    Object.values(metaAuswahl).some(v => v) || Object.values(rawKatAuswahl).some(v => v)
  );

  async function metadatenSuchen(quelle) {
    if (metaLaden || !book) return;
    metaLaden = true;
    const quelleLabels = { google_books: "Google Books", open_library: "Open Library", wikipedia: "Wikipedia/Wikidata" };
    const quelleLabel = quelleLabels[quelle] || "allen Quellen";
    metaSchritt = `Suche in ${quelleLabel}...`;
    metaFehler = "";
    metaVorschlag = null;
    metaAktuell = null;
    metaAuswahl = {};
    rawOffen = false;
    rawKatAuswahl = {};

    try {
      const result = await sucheMetadaten(book.id, quelle);
      if (!result.angereichert) {
        metaFehler = result.grund || "Keine Metadaten gefunden";
        return;
      }
      metaVorschlag = result.vorschlag;
      metaAktuell = result.aktuell;
      metaQuelle = result.quelle || "";
      metaAuswahl = metaInitAuswahl(result.vorschlag);
      metaSchritt = "";
    } catch (e) {
      metaFehler = e.message || "Fehler bei der Suche";
    } finally {
      metaLaden = false;
    }
  }

  async function metadatenUebernehmen() {
    if (!metaVorschlag || metaLaden || !metaHatAuswahl) return;
    metaLaden = true;
    metaSchritt = "Daten werden übernommen...";
    metaFehler = "";

    try {
      const payload = {};
      for (const feld of vergleichsFelder) {
        if (metaAuswahl[feld.key]) {
          payload[feld.key] = metaVorschlag[feld.key];
        }
      }
      if (metaAuswahl.cover && metaVorschlag.cover_url) {
        payload.cover_url = metaVorschlag.cover_url;
        payload.quelle = metaQuelle;
        metaSchritt = "Cover wird heruntergeladen...";
      }
      if (metaAuswahl.kategorien && metaVorschlag.kategorien?.length) {
        payload.kategorien = [...metaVorschlag.kategorien];
      }
      // Einzelne Raw-Listen als Kategorien dazu
      if (metaVorschlag.raw) {
        for (const [key, checked] of Object.entries(rawKatAuswahl)) {
          if (checked) {
            const werte = metaVorschlag.raw[key];
            if (Array.isArray(werte)) {
              if (!payload.kategorien) payload.kategorien = [];
              for (const w of werte) {
                if (typeof w === "string" && w && !payload.kategorien.includes(w)) {
                  payload.kategorien.push(w);
                }
              }
            }
          }
        }
      }
      await uebernehmMetadaten(book.id, payload);
      metaSchritt = "Buch wird neu geladen...";
      await ladeBuch(book.id);
      metaVorschlag = null;
      metaAktuell = null;
      metaAuswahl = {};
      metaSchritt = "";
      coverError = false;
    } catch (e) {
      metaFehler = e.message || "Fehler beim Übernehmen";
    } finally {
      metaLaden = false;
    }
  }

  function metadatenVerwerfen() {
    metaVorschlag = null;
    metaAktuell = null;
    metaAuswahl = {};
    metaSchritt = "";
    metaFehler = "";
    rawOffen = false;
    rawKatAuswahl = {};
    volltextOffen = false;
    volltextInhalt = "";
    volltextVon = 1;
    volltextBis = 5;
    volltextSeitenGesamt = 0;
  }

  $effect(() => {
    ladeBuch(Number(params.id));
  });

  async function ladeBuch(id) {
    laden = true;
    fehler = null;
    try {
      book = await holeBuch(id);
      // Aehnliche Buecher + Markierungen im Hintergrund laden
      aehnlicheBuecher(id).then(r => { aehnliche = r; }).catch(() => {});
      ladeMarkierungen(id);
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  async function ladeMarkierungen(id) {
    try {
      markierungen = await highlightsFuerBuch(id);
    } catch {
      markierungen = [];
    }
  }

  async function onMarkierungLoeschen(hlId) {
    try {
      await loescheHighlight(hlId);
      markierungen = markierungen.filter(m => m.id !== hlId);
    } catch {}
  }

  let hlEditTimer = {};
  function onHlNotizAendern(hlId, neueNotiz) {
    markierungen = markierungen.map(m => m.id === hlId ? { ...m, label_note: neueNotiz } : m);
    clearTimeout(hlEditTimer["note_" + hlId]);
    hlEditTimer["note_" + hlId] = setTimeout(async () => {
      try { await aktualisiereHighlight(hlId, { label_note: neueNotiz }); } catch {}
    }, 800);
  }

  function onHlNameAendern(hlId, neuerName) {
    markierungen = markierungen.map(m => m.id === hlId ? { ...m, label_name: neuerName } : m);
    clearTimeout(hlEditTimer["name_" + hlId]);
    hlEditTimer["name_" + hlId] = setTimeout(async () => {
      try { await aktualisiereHighlight(hlId, { label_name: neuerName }); } catch {}
    }, 800);
  }

  async function onFavoritToggle() {
    if (!book) return;
    try {
      const result = await toggleFavorit(book.id);
      book = { ...book, is_favorite: result.ist_favorit ?? result.is_favorite };
      notifyBooksChanged();
    } catch { /* still */ }
  }

  async function onZumLesenToggle() {
    if (!book) return;
    try {
      const result = await toggleZumLesen(book.id);
      book = { ...book, is_to_read: result.zu_lesen ?? result.is_to_read };
      notifyBooksChanged();
    } catch { /* still */ }
  }

  let istGelesen = $derived(book?.last_read_at != null);

  async function onGelesenToggle() {
    if (!book) return;
    try {
      const result = await toggleGelesen(book.id);
      book = { ...book, last_read_at: result.gelesen ? new Date().toISOString() : null };
      notifyBooksChanged();
    } catch { /* still */ }
  }

  async function onRate(rating) {
    if (!book) return;
    try {
      const result = await setzeBewertung(book.id, rating);
      book = { ...book, rating: result.bewertung ?? result.rating };
    } catch { /* still */ }
  }

  const papierLabel = { normal: "Normal", sepia: "Sepia", dunkel: "Dunkel" };
  const ansichtLabel = { breite: "Seitenbreite", seite: "Ganze Seite" };

  function parseLeseposition(pos, format) {
    if (!pos) return { items: [], fontPreview: null, page: null, percent: null };
    const items = [];
    let fontPreview = null;
    let page = null;
    let percent = null;

    if (pos.startsWith("pdf:")) {
      try {
        const d = JSON.parse(pos.slice(4));
        if (d.page) { items.push({ label: "Seite", value: d.page }); page = d.page; }
        if (d.zoom) items.push({ label: "Zoom", value: `${d.zoom}%` });
        if (d.ansicht) items.push({ label: "Ansicht", value: d.ansicht, type: "pdf-ansicht" });
        if (d.papier) items.push({ label: "Papier", value: d.papier, type: "papier" });
      } catch { items.push({ label: "Position", value: pos }); }
    } else if (pos.startsWith("epub:")) {
      try {
        const d = JSON.parse(pos.slice(5));
        if (d.percent > 0) percent = Math.round(d.percent);
        if (d.fontSize) items.push({ label: "Schrift", value: `${d.fontSize}%` });
        if (d.fontFamily) {
          fontPreview = {
            family: d.fontFamily,
            name: d.fontFamily.split(",")[0].trim(),
            fg: d.fgColor || null,
            bg: d.bgColor || null,
          };
        }
        if (d.lineHeight) items.push({ label: "Zeilenabstand", value: `${d.lineHeight}` });
        if (d.singlePage != null) items.push({ label: "Layout", value: d.singlePage ? "single" : "double", type: "layout" });
        if (d.maxWidthSingle) items.push({ label: "Breite (1-seitig)", value: `${d.maxWidthSingle}px` });
        if (d.maxWidthDouble) items.push({ label: "Breite (2-seitig)", value: `${d.maxWidthDouble}px` });
      } catch { items.push({ label: "Position", value: pos }); }
    } else if (pos.startsWith("txt:")) {
      const rest = pos.slice(4);
      if (rest.startsWith("{")) {
        try {
          const d = JSON.parse(rest);
          if (d.scrollPct != null) { items.push({ label: "Fortschritt", value: `${d.scrollPct}%` }); percent = Math.round(d.scrollPct); }
          if (d.fontSize) items.push({ label: "Schrift", value: `${d.fontSize}%` });
          if (d.papier) items.push({ label: "Papier", value: d.papier, type: "papier" });
        } catch { items.push({ label: "Position", value: pos }); }
      } else {
        items.push({ label: "Fortschritt", value: `${rest}%` });
      }
    } else if (pos.startsWith("cfi:")) {
      items.push({ label: "EPUB-Position", value: "Gespeichert" });
    } else {
      const m = pos.match(/page:(\d+)/);
      if (m) { items.push({ label: "Seite", value: m[1] }); page = parseInt(m[1]); }
      else items.push({ label: "Position", value: pos });
    }

    return { items, fontPreview, page, percent };
  }
</script>

{#if book}
  {#if !coverError && book.cover_path}
    <div class="bg-cover-blur" style="background-image: url({coverUrl(book.id, book.updated_at)})"></div>
  {:else}
    <div class="bg-cover-blur bg-cover-default" style="background-image: url(/api/config/design/hintergrund/{ui.bgAktuellerDateiname || ''}?token={encodeURIComponent(getToken())})"></div>
  {/if}
  <div class="bg-cover-overlay"></div>
{/if}

<div class="book-detail">
  <div class="page-header">
    <a href="/" class="back-link"><i class="fa-solid fa-arrow-left"></i> Bibliothek</a>
  </div>

  {#if laden}
    <p class="status-text">Buch wird geladen...</p>
  {:else if fehler}
    <p class="status-text error">Fehler: {fehler}</p>
  {:else if book}
    <div class="detail-layout">
      <div class="cover-section">
        <div class="cover-wrapper">
          {#if !coverError}
            <img
              src={coverUrl(book.id, book.updated_at)}
              alt="Cover: {book.title}"
              class="cover-image"
              onerror={() => (coverError = true)}
            />
          {:else}
            <div class="cover-placeholder">
              <span>{(book.file_format || "?").toUpperCase()}</span>
            </div>
          {/if}
          <div class="cover-overlay">
            {#if book.reading_position}
              {@const pos = parseLeseposition(book.reading_position, book.file_format)}
              <a href="/book/{book.id}/read" class="cover-btn cover-btn-tl" title={pos.page && book.page_count ? `Auf Seite ${pos.page} von ${book.page_count} weiterlesen` : pos.percent ? `Bei ${pos.percent}% weiterlesen` : 'Weiterlesen'}>
                <i class="fa-solid fa-bookmark"></i>
              </a>
              <a href="/book/{book.id}/read?restart=1" class="cover-btn cover-btn-tr" title="Von vorne lesen">
                <i class="fa-solid fa-rotate-left"></i>
              </a>
            {:else}
              <a href="/book/{book.id}/read" class="cover-btn cover-btn-tl" title="Lesen">
                <i class="fa-solid fa-bookmark"></i>
              </a>
            {/if}
            <a href="/api/books/{book.id}/file?token={encodeURIComponent(getToken())}" download={book.file_name || true} class="cover-btn cover-btn-bl" title="Buchdatei herunterladen">
              <i class="fa-solid fa-download"></i>
            </a>
          </div>
        </div>

        {#if book.reading_position}
          {@const pos = parseLeseposition(book.reading_position, book.file_format)}
          {#if pos.items.length > 0}
            <div class="position-details">
              {#each pos.items as item}
                <div class="pos-item">
                  <span class="pos-label">{item.label}</span>
                  {#if item.type === "layout"}
                    <span class="pos-value pos-icon" title={item.value === "single" ? "Einzelseite" : "Doppelseite"}>
                      {#if item.value === "single"}
                        <svg width="16" height="14" viewBox="0 0 16 14"><rect x="3" y="0" width="10" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {:else}
                        <svg width="20" height="14" viewBox="0 0 20 14"><rect x="0.75" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="11.25" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {/if}
                    </span>
                  {:else if item.type === "pdf-ansicht"}
                    <span class="pos-value pos-icon" title={ansichtLabel[item.value] || item.value}>
                      {#if item.value === "scroll"}
                        <svg width="14" height="14" viewBox="0 0 14 14"><rect x="1" y="0" width="12" height="5.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="1" y="8.5" width="12" height="5.5" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
                      {:else if item.value === "breite"}
                        <svg width="18" height="14" viewBox="0 0 18 14"><rect x="0.75" y="1" width="16.5" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><line x1="4" y1="5" x2="14" y2="5" stroke="currentColor" stroke-width="1" opacity="0.4"/><line x1="4" y1="7.5" x2="12" y2="7.5" stroke="currentColor" stroke-width="1" opacity="0.4"/><line x1="4" y1="10" x2="13" y2="10" stroke="currentColor" stroke-width="1" opacity="0.4"/></svg>
                      {:else if item.value === "seite"}
                        <svg width="12" height="14" viewBox="0 0 12 14"><rect x="0.75" y="0" width="10.5" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
                      {:else if item.value === "einzeln"}
                        <svg width="16" height="14" viewBox="0 0 16 14"><rect x="3" y="0" width="10" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {:else if item.value === "doppel"}
                        <svg width="20" height="14" viewBox="0 0 20 14"><rect x="0.75" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="11.25" y="0" width="8" height="14" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
                      {/if}
                    </span>
                  {:else if item.type === "papier"}
                    <span class="pos-value pos-papier pos-papier-{item.value}" title={papierLabel[item.value] || item.value}></span>
                  {:else}
                    <span class="pos-value">{item.value}</span>
                  {/if}
                </div>
              {/each}
              {#if pos.fontPreview}
                <div class="pos-item">
                  <span class="pos-label">Schriftart</span>
                  <span
                    class="pos-font-preview"
                    style="font-family: {pos.fontPreview.family}; {pos.fontPreview.fg ? `color: ${pos.fontPreview.fg};` : ''} {pos.fontPreview.bg ? `background-color: ${pos.fontPreview.bg};` : ''}"
                  >{pos.fontPreview.name}</span>
                </div>
              {/if}
            </div>
          {/if}
        {/if}
      </div>

      <div class="info-section">
        {#if editMode}
          <div class="edit-form">
            <div class="edit-field">
              <label class="edit-label" for="edit-titel">Titel</label>
              <input type="text" class="edit-input" id="edit-titel" bind:value={editData.title} />
            </div>
            <div class="edit-field">
              <label class="edit-label" for="edit-autor">Autor</label>
              <input type="text" class="edit-input" id="edit-autor" bind:value={editData.author} />
            </div>
            <div class="edit-row">
              <div class="edit-field">
                <label class="edit-label" for="edit-isbn">ISBN</label>
                <div class="edit-isbn-row">
                  <input type="text" class="edit-input mono" id="edit-isbn" bind:value={editData.isbn} />
                  <button class="btn btn-sm btn-secondary" onclick={isbnScannen} disabled={isbnScanLaden} title="ISBN aus Buch extrahieren">
                    {#if isbnScanLaden}
                      <i class="fa-solid fa-spinner fa-spin"></i>
                    {:else}
                      <i class="fa-solid fa-barcode"></i>
                    {/if}
                  </button>
                </div>
              </div>
              <div class="edit-field">
                <label class="edit-label" for="edit-jahr">Jahr</label>
                <input type="number" class="edit-input" id="edit-jahr" bind:value={editData.year} />
              </div>
            </div>
            {#if isbnScanErgebnis}
              <div class="isbn-scan-ergebnis">
                {#if isbnScanErgebnis.gefunden.length === 0}
                  <span class="isbn-scan-leer">Keine ISBN im Buch gefunden</span>
                {:else}
                  <span class="isbn-scan-titel">Gefundene ISBNs:</span>
                  {#each isbnScanErgebnis.gefunden as eintrag}
                    <div class="isbn-scan-gruppe">
                      {#if eintrag.isbn13}
                        <button class="isbn-chip" onclick={() => isbnUebernehmen(eintrag.isbn13)}>
                          ISBN-13: {eintrag.isbn13}
                        </button>
                      {/if}
                      {#if eintrag.isbn10}
                        <button class="isbn-chip" onclick={() => isbnUebernehmen(eintrag.isbn10)}>
                          ISBN-10: {eintrag.isbn10}
                        </button>
                      {/if}
                    </div>
                  {/each}
                {/if}
              </div>
            {/if}
            <div class="edit-row">
              <div class="edit-field">
                <label class="edit-label" for="edit-verlag">Verlag</label>
                <input type="text" class="edit-input" id="edit-verlag" bind:value={editData.publisher} />
              </div>
              <div class="edit-field">
                <label class="edit-label" for="edit-sprache">Sprache</label>
                <input type="text" class="edit-input" id="edit-sprache" bind:value={editData.language} />
              </div>
            </div>
            <div class="edit-row">
              <div class="edit-field">
                <label class="edit-label" for="edit-seiten">Seiten</label>
                <input type="number" class="edit-input" id="edit-seiten" bind:value={editData.page_count} />
              </div>
              <div class="edit-field">
                <label class="edit-label" for="edit-typ">Typ</label>
                <select class="edit-input" id="edit-typ" bind:value={editData.typ}>
                  <option value="">-- Buch (Standard) --</option>
                  <option value="heft">Heft</option>
                  <option value="katalog">Katalog</option>
                  <option value="broschuere">Broschüre</option>
                </select>
              </div>
            </div>
            <div class="edit-row">
              <div class="edit-field">
                <label class="edit-label" for="edit-sammlung">Sammlung</label>
                <select class="edit-input" id="edit-sammlung" bind:value={editData.sammlung_id}>
                  <option value="">-- Keine --</option>
                  {#each sammlungen as s (s.id)}
                    <option value={s.id}>{s.name}</option>
                  {/each}
                </select>
              </div>
              {#if editData.sammlung_id}
                <div class="edit-field">
                  <label class="edit-label" for="edit-band">Bandnummer</label>
                  <input type="text" class="edit-input" id="edit-band" bind:value={editData.band_nummer} placeholder="z.B. 42, VII, S1" />
                </div>
              {/if}
            </div>
            <div class="edit-field">
              <label class="edit-label" for="edit-beschreibung">Beschreibung</label>
              <textarea class="edit-input edit-textarea" id="edit-beschreibung" bind:value={editData.description} rows="3"></textarea>
            </div>
            <div class="edit-aktionen">
              <button class="btn btn-primary btn-sm" onclick={saveEdit} disabled={editSpeichern}>
                {#if editSpeichern}
                  <i class="fa-solid fa-spinner fa-spin"></i>
                {/if}
                Speichern
              </button>
              <button class="btn btn-secondary btn-sm" onclick={cancelEdit}>Abbrechen</button>
            </div>
          </div>
        {:else}
          <h1 class="book-title">{book.title}</h1>
          {#if book.authors && book.authors.length > 0}
            <div class="book-authors">
              {#each book.authors as a, i (a.id)}
                <a href="/author/{a.id}" class="author-link">{a.name}</a>{#if i < book.authors.length - 1}<span class="author-sep">,</span>{/if}
              {/each}
            </div>
          {:else}
            <p class="book-author">{book.author || "Unbekannter Autor"}</p>
          {/if}
          {#if book.publisher}
            <p class="book-publisher">{book.publisher}</p>
          {/if}
        {/if}

        <div class="rating-row">
          <RatingStars rating={book.rating} interactive onRate={onRate} />
        </div>

        <div class="action-groups">
          <div class="action-grid">
            {#if !editMode}
              <button class="action-btn" onclick={startEdit} title="Buchdetails bearbeiten">
                <i class="fa-solid fa-pen"></i> Bearbeiten
              </button>
            {/if}
            <button class="action-btn" class:active={book.is_favorite} onclick={onFavoritToggle} title="{book.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'}">
              <i class="{book.is_favorite ? 'fa-solid' : 'fa-regular'} fa-heart"></i> Favorit
            </button>
            <button class="action-btn" class:active={book.is_to_read} onclick={onZumLesenToggle} title="{book.is_to_read ? 'Vom Lesesofa nehmen' : 'Aufs Lesesofa legen'}">
              <i class="fa-solid {book.is_to_read ? 'fa-bookmark' : 'fa-plus'}"></i> Lesesofa
            </button>
            <button class="action-btn" class:active={istGelesen} onclick={onGelesenToggle} title="{istGelesen ? 'Als ungelesen markieren' : 'Als gelesen markieren'}">
              <i class="fa-solid {istGelesen ? 'fa-book-open' : 'fa-book'}"></i> {istGelesen ? "Gelesen" : "Ungelesen"}
            </button>
            <button class="action-btn" onclick={() => (aiDialogOpen = true)} title="KI-Kategorisierung starten">
              <i class="fa-solid fa-wand-magic-sparkles"></i> Kategorisieren
            </button>
          </div>
          <div class="action-grid">
            <button class="action-btn meta-btn" class:loading={metaLaden} onclick={() => metadatenSuchen("google_books")} disabled={metaLaden} title="Metadaten bei Google Books suchen">
              {#if metaLaden && metaSchritt.includes("Google")}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-solid fa-g"></i>
              {/if} Google Books
            </button>
            <button class="action-btn meta-btn" class:loading={metaLaden} onclick={() => metadatenSuchen("open_library")} disabled={metaLaden} title="Metadaten bei Open Library suchen">
              {#if metaLaden && metaSchritt.includes("Open")}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-solid fa-book-open"></i>
              {/if} Open Library
            </button>
            <button class="action-btn meta-btn" class:loading={metaLaden} onclick={() => metadatenSuchen("wikipedia")} disabled={metaLaden} title="Metadaten bei Wikipedia/Wikidata suchen">
              {#if metaLaden && metaSchritt.includes("Wikipedia")}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-brands fa-wikipedia-w"></i>
              {/if} Wikipedia
            </button>
            <button class="action-btn meta-btn" class:loading={volltextLaden} onclick={() => { volltextOffen = !volltextOffen; if (volltextOffen && !volltextInhalt) volltextLadenAktion(); }} disabled={volltextLaden} title="Beschreibung aus dem Buchtext übernehmen">
              {#if volltextLaden}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-solid fa-file-lines"></i>
              {/if} Aus Buch
            </button>
            <button class="action-btn meta-btn" class:loading={coverNeuLaden} onclick={coverNeuExtrahieren} disabled={coverNeuLaden} title="Cover neu aus der Buchdatei extrahieren">
              {#if coverNeuLaden}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-solid fa-image"></i>
              {/if} Cover neu
            </button>
          </div>
        </div>

        {#if volltextOffen && !metaVorschlag}
          <div class="meta-vergleich">
            <div class="meta-header">
              <h2 class="section-title">Beschreibung aus Buchtext</h2>
            </div>
            <div class="volltext-seiten-ctrl">
              <label>
                Seite <input type="number" class="volltext-seite-input" bind:value={volltextVon} min="1" max={volltextSeitenGesamt || 999} />
              </label>
              <span>bis</span>
              <label>
                <input type="number" class="volltext-seite-input" bind:value={volltextBis} min={volltextVon} max={volltextSeitenGesamt || 999} />
              </label>
              {#if volltextSeitenGesamt}
                <span class="volltext-seiten-info">von {volltextSeitenGesamt}</span>
              {/if}
              <button class="btn btn-secondary btn-sm" onclick={volltextLadenAktion} disabled={volltextLaden}>
                {#if volltextLaden}
                  <i class="fa-solid fa-spinner fa-spin"></i>
                {:else}
                  <i class="fa-solid fa-sync"></i>
                {/if}
                Laden
              </button>
            </div>
            {#if volltextLaden}
              <div class="volltext-laden"><i class="fa-solid fa-spinner fa-spin"></i> Volltext wird geladen...</div>
            {:else if volltextInhalt}
              <div class="volltext-vorschau">
                <textarea class="volltext-textarea" bind:value={volltextInhalt}></textarea>
                <div class="meta-aktionen">
                  <button class="btn btn-primary btn-sm" onclick={() => volltextDirektUebernehmen()}>
                    <i class="fa-solid fa-check"></i> Als Beschreibung speichern
                  </button>
                  <button class="btn btn-secondary btn-sm" onclick={() => { volltextOffen = false; volltextInhalt = ""; }}>
                    Abbrechen
                  </button>
                </div>
              </div>
            {:else}
              <p class="volltext-leer">Kein Volltext vorhanden.</p>
            {/if}
          </div>
        {/if}

        {#if metaLaden && metaSchritt}
          <div class="meta-status">
            <i class="fa-solid fa-spinner fa-spin"></i>
            <span>{metaSchritt}</span>
          </div>
        {/if}

        {#if metaFehler}
          <div class="meta-status meta-fehler">
            <i class="fa-solid fa-triangle-exclamation"></i>
            <span>{metaFehler}</span>
          </div>
        {/if}

        {#if metaVorschlag && metaAktuell}
          <div class="meta-vergleich">
            <div class="meta-header">
              <h2 class="section-title">Metadaten-Vergleich</h2>
              <span class="meta-quelle">{{ google_books: "Google Books", open_library: "Open Library", wikipedia: "Wikipedia/Wikidata" }[metaQuelle] || metaQuelle}</span>
            </div>

            <div class="vergleich-tabelle">
              <div class="vergleich-kopf">
                <span class="vergleich-check"></span>
                <span class="vergleich-label"></span>
                <span class="vergleich-spalte">Aktuell</span>
                <span class="vergleich-spalte">Vorschlag</span>
              </div>
              {#each vergleichsFelder as feld}
                {@const alt = metaAktuell[feld.key] ?? ""}
                {@const neu = metaVorschlag[feld.key] ?? ""}
                {#if neu || alt}
                  {@const geaendert = String(neu) !== String(alt) && !!neu}
                  {@const hatVorschlag = !!neu}
                  <label class="vergleich-zeile" class:geaendert={geaendert && metaAuswahl[feld.key]} class:ausgewaehlt={metaAuswahl[feld.key]}>
                    <span class="vergleich-check">
                      {#if hatVorschlag}
                        <input type="checkbox" bind:checked={metaAuswahl[feld.key]} />
                      {/if}
                    </span>
                    <span class="vergleich-label">{feld.label}</span>
                    <span class="vergleich-alt" class:leer={!alt}>{alt || "-"}</span>
                    <span class="vergleich-neu" class:leer={!neu} class:identisch={!geaendert && !!neu} class:abgewaehlt={hatVorschlag && !metaAuswahl[feld.key]}>{neu || "-"}</span>
                  </label>
                {/if}
              {/each}

              {#if metaVorschlag.cover_url}
                <label class="vergleich-zeile" class:geaendert={metaAuswahl.cover}>
                  <span class="vergleich-check">
                    <input type="checkbox" bind:checked={metaAuswahl.cover} />
                  </span>
                  <span class="vergleich-label">Cover</span>
                  <span class="vergleich-alt">
                    {#if metaAktuell.hat_cover}
                      <img src={coverUrl(book.id, book.updated_at)} alt="Aktuelles Cover" class="cover-vorschau" />
                    {:else}
                      -
                    {/if}
                  </span>
                  <span class="vergleich-neu" class:abgewaehlt={!metaAuswahl.cover}>
                    <div class="cover-vorschau-wrap">
                      <img src={metaVorschlag.cover_url} alt="Vorgeschlagenes Cover" class="cover-vorschau" />
                      <img src={metaVorschlag.cover_url} alt="Vorgeschlagenes Cover" class="cover-gross" />
                    </div>
                  </span>
                </label>
              {/if}

              {#if metaVorschlag.kategorien && metaVorschlag.kategorien.length > 0}
                <label class="vergleich-zeile" class:geaendert={metaAuswahl.kategorien}>
                  <span class="vergleich-check">
                    <input type="checkbox" bind:checked={metaAuswahl.kategorien} />
                  </span>
                  <span class="vergleich-label">Kategorien</span>
                  <span class="vergleich-alt">{metaAktuell.kategorien?.length || 0}</span>
                  <span class="vergleich-neu" class:abgewaehlt={!metaAuswahl.kategorien}>+{metaVorschlag.kategorien.length}</span>
                </label>
                {#if metaAuswahl.kategorien}
                  <div class="meta-kategorien">
                    {#each metaVorschlag.kategorien.slice(0, 20) as kat}
                      <span class="meta-kat-chip">{kat}</span>
                    {/each}
                    {#if metaVorschlag.kategorien.length > 20}
                      <span class="meta-kat-more">+{metaVorschlag.kategorien.length - 20} weitere</span>
                    {/if}
                  </div>
                {/if}
              {/if}
            </div>

            {#if metaVorschlag.raw && Object.keys(metaVorschlag.raw).length > 0}
              <div class="raw-section">
                <button class="raw-toggle" onclick={() => rawOffen = !rawOffen}>
                  <i class="fa-solid {rawOffen ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                  Alle Daten ({Object.keys(metaVorschlag.raw).length} Felder)
                </button>
                {#if rawOffen}
                  <div class="raw-liste">
                    {#each Object.entries(metaVorschlag.raw) as [key, value]}
                      <div class="raw-eintrag">
                        <span class="raw-key">{key}</span>
                        <div class="raw-value-wrap">
                          {#if Array.isArray(value) && value.length > 0 && value.every(v => typeof v === "string")}
                            <div class="raw-chips">
                              {#each value as v}
                                <span class="raw-chip">{v}</span>
                              {/each}
                            </div>
                            <label class="raw-kat-check" title="Als Kategorien übernehmen">
                              <input type="checkbox" bind:checked={rawKatAuswahl[key]} />
                              <span class="raw-kat-label">als Kategorien</span>
                            </label>
                          {:else if typeof value === "object" && value !== null}
                            <code class="raw-json">{JSON.stringify(value, null, 2)}</code>
                          {:else}
                            <span class="raw-text">{String(value)}</span>
                          {/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}

            <div class="raw-section">
              <button class="raw-toggle" onclick={() => { volltextOffen = !volltextOffen; if (volltextOffen && !volltextInhalt) volltextLadenAktion(); }}>
                <i class="fa-solid {volltextOffen ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                Beschreibung aus Buchtext
              </button>
              {#if volltextOffen}
                <div class="volltext-seiten-ctrl">
                  <label>
                    Seite <input type="number" class="volltext-seite-input" bind:value={volltextVon} min="1" max={volltextSeitenGesamt || 999} />
                  </label>
                  <span>bis</span>
                  <label>
                    <input type="number" class="volltext-seite-input" bind:value={volltextBis} min={volltextVon} max={volltextSeitenGesamt || 999} />
                  </label>
                  {#if volltextSeitenGesamt}
                    <span class="volltext-seiten-info">von {volltextSeitenGesamt}</span>
                  {/if}
                  <button class="btn btn-secondary btn-sm" onclick={volltextLadenAktion} disabled={volltextLaden}>
                    {#if volltextLaden}
                      <i class="fa-solid fa-spinner fa-spin"></i>
                    {:else}
                      <i class="fa-solid fa-sync"></i>
                    {/if}
                    Laden
                  </button>
                </div>
                {#if volltextLaden}
                  <div class="volltext-laden"><i class="fa-solid fa-spinner fa-spin"></i> Volltext wird geladen...</div>
                {:else if volltextInhalt}
                  <div class="volltext-vorschau">
                    <textarea class="volltext-textarea" bind:value={volltextInhalt}></textarea>
                    <div class="meta-aktionen">
                      <button class="btn btn-primary btn-sm" onclick={() => volltextUebernehmen(volltextInhalt)}>
                        <i class="fa-solid fa-check"></i> Als Beschreibung übernehmen
                      </button>
                      <button class="btn btn-secondary btn-sm" onclick={() => { volltextOffen = false; volltextInhalt = ""; }}>
                        <i class="fa-solid fa-xmark"></i> Verwerfen
                      </button>
                    </div>
                  </div>
                {:else}
                  <p class="volltext-leer">Kein Volltext vorhanden.</p>
                {/if}
              {/if}
            </div>

            <div class="meta-aktionen">
              <button class="btn btn-primary btn-sm" onclick={metadatenUebernehmen} disabled={metaLaden || !metaHatAuswahl}>
                {#if metaLaden}
                  <i class="fa-solid fa-spinner fa-spin"></i>
                {/if}
                Ausgewählte übernehmen
              </button>
              <button class="btn btn-secondary btn-sm" onclick={metadatenVerwerfen}>
                Verwerfen
              </button>
            </div>
          </div>
        {/if}

        <div class="meta-section">
          <h2 class="section-title">Details</h2>
          <BookMeta {book} />
        </div>

        {#if book.description}
          <div class="meta-section">
            <h2 class="section-title">Beschreibung</h2>
            <p class="buch-beschreibung">{book.description}</p>
          </div>
        {/if}

        <div class="tags-section">
          <div class="kat-header">
            <h2 class="section-title">Kategorien ({book.categories?.length || 0})</h2>
            <button
              class="kat-edit-btn"
              onclick={() => katEditMode ? katEditBeenden() : katEditStarten()}
              title={katEditMode ? "Bearbeitung beenden" : "Kategorien bearbeiten"}
            >
              <i class="fa-solid {katEditMode ? 'fa-check' : 'fa-pen'}"></i>
            </button>
          </div>

          {#if katEditMode}
            <div class="kat-edit-area">
              {#if book.categories && book.categories.length > 0}
                <div class="chip-list">
                  {#each book.categories as cat (cat.id)}
                    <span class="chip kat-chip-edit">
                      {cat.name}
                      <button class="kat-remove-btn" onclick={() => kategorieEntfernen(cat.id)} title="Kategorie entfernen">
                        <i class="fa-solid fa-xmark"></i>
                      </button>
                    </span>
                  {/each}
                </div>
              {:else}
                <p class="kat-leer">Keine Kategorien zugewiesen</p>
              {/if}

              <div class="kat-suche-wrap">
                <i class="fa-solid fa-search kat-suche-icon"></i>
                <input
                  class="kat-suche-input"
                  type="text"
                  placeholder="Kategorie suchen..."
                  value={katSuche}
                  oninput={(e) => katSuche = e.target.value}
                />
              </div>

              {#if katGefiltert().length > 0}
                <div class="kat-ergebnisse">
                  {#each katGefiltert() as cat (cat.id)}
                    <button class="kat-ergebnis" onclick={() => kategorieHinzufuegen(cat.id)}>
                      <i class="fa-solid fa-plus kat-plus-icon"></i>
                      {cat.name}
                      {#if cat.buch_anzahl != null}
                        <span class="kat-count">({cat.buch_anzahl})</span>
                      {/if}
                    </button>
                  {/each}
                </div>
              {:else if katSuche.trim().length > 0}
                <p class="kat-leer">Keine passenden Kategorien gefunden</p>
              {/if}
            </div>
          {:else if book.categories && book.categories.length > 0}
            <div class="chip-list">
              {#each (kategorienAlle ? book.categories : book.categories.slice(0, 5)) as cat (cat.id)}
                <a href="/?category={cat.id}" class="chip">{cat.name}</a>
              {/each}
              {#if book.categories.length > 5}
                <button class="chip chip-toggle" onclick={() => kategorienAlle = !kategorienAlle}>
                  {kategorienAlle ? "weniger" : `+${book.categories.length - 5} weitere`}
                </button>
              {/if}
            </div>
          {/if}
        </div>

        {#if book.sammlung}
          <div class="tags-section">
            <h2 class="section-title">Sammlung</h2>
            <div class="chip-list">
              <a
                href="/?sammlung={book.sammlung.id}"
                class="chip sammlung-chip"
                style="--sammlung-color: {book.sammlung.color || 'var(--color-accent)'}"
              >
                <span class="sammlung-dot" style="background: {book.sammlung.color || 'var(--color-accent)'}"></span>
                {book.sammlung.name}
                {#if book.band_nummer}
                  <span class="band-nr">#{book.band_nummer}</span>
                {/if}
              </a>
            </div>
          </div>
        {/if}

        {#if book.typ}
          <div class="tags-section">
            <h2 class="section-title">Typ</h2>
            <div class="chip-list">
              <span class="chip typ-chip">
                {{ heft: "Heft", katalog: "Katalog", broschuere: "Broschüre" }[book.typ] || book.typ}
              </span>
            </div>
          </div>
        {/if}

      </div>
    </div>

    <div class="notes-section">
        <NoteList bookId={book.id} />
      </div>

    <!-- Markierungen / Labels -->
    {#if markierungen.length > 0}
      <div class="labels-section">
        <h3 class="section-title"><i class="fa-solid fa-highlighter"></i> Markierungen ({markierungen.length})</h3>
        <div class="labels-list" class:labels-scrollable={markierungen.length > 5}>
          {#each markierungen as hl (hl.id)}
            <div class="label-item-wrap">
              <div class="label-item">
                <i class="fa-solid fa-bookmark label-icon" style="color: {hl.color}"></i>
                {#if hl.label_name}
                  <span class="label-name">{hl.label_name}</span>
                {:else}
                  <span class="label-snippet">{hl.text_snippet?.slice(0, 40) || "Markierung"}{hl.text_snippet?.length > 40 ? "..." : ""}</span>
                {/if}
                {#if hl.cfi_range}
                  <button
                    class="label-page"
                    onclick={() => {
                      navigate(`/book/${book.id}/read?cfi=${encodeURIComponent(hl.cfi_range)}`);
                    }}
                    title="Zur markierten Stelle springen"
                  >
                    <i class="fa-solid fa-arrow-up-right-from-square"></i>
                  </button>
                {/if}
                <button
                  class="label-expand"
                  class:has-note={!!hl.label_note || !!hl.label_name}
                  onclick={() => { markierungOffen = { ...markierungOffen, [hl.id]: !markierungOffen[hl.id] }; }}
                  title={markierungOffen[hl.id] ? "Einklappen" : "Bearbeiten"}
                >
                  <i class="fa-solid fa-chevron-{markierungOffen[hl.id] ? 'up' : 'down'}"></i>
                </button>
                <button class="label-delete" onclick={() => onMarkierungLoeschen(hl.id)} title="Markierung löschen">
                  <i class="fa-solid fa-trash-can"></i>
                </button>
              </div>
              {#if markierungOffen[hl.id]}
                <div class="label-edit-fields">
                  <input
                    class="label-name-edit"
                    type="text"
                    placeholder="Label-Name (optional)"
                    value={hl.label_name || ""}
                    oninput={(e) => onHlNameAendern(hl.id, e.target.value)}
                    maxlength="50"
                  />
                  <textarea
                    class="label-note-edit"
                    placeholder="Notiz zur Markierung..."
                    value={hl.label_note || ""}
                    oninput={(e) => onHlNotizAendern(hl.id, e.target.value)}
                    rows={Math.max(2, Math.min(10, (hl.label_note || "").split("\n").length + 1))}
                  ></textarea>
                  {#if hl.text_snippet}
                    <div class="label-text-snippet">{hl.text_snippet}</div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Buch-Volltextsuche -->
    <div class="book-search-section">
      <button class="book-search-toggle" onclick={() => { buchSucheOffen = !buchSucheOffen; }} title="Volltextsuche im Buchinhalt">
        <i class="fa-solid fa-magnifying-glass"></i>
        Im Buch suchen
        <i class="fa-solid fa-chevron-{buchSucheOffen ? 'up' : 'down'}" style="margin-left: auto; font-size: 0.75rem;"></i>
      </button>
      {#if buchSucheOffen}
        <div class="book-search-body">
          <div class="book-search-row">
            <input
              type="text"
              class="book-search-input"
              placeholder="Suchbegriff eingeben..."
              value={buchSuchbegriff}
              oninput={onBuchSuche}
            />
            <div class="book-search-filters">
              <button
                class="search-filter-btn"
                class:active={suchGanzesWort}
                onclick={() => toggleSuchFilter("wort")}
                title="Nur ganze Wörter suchen"
              >Ab</button>
              <button
                class="search-filter-btn"
                class:active={suchGrossKlein}
                onclick={() => toggleSuchFilter("case")}
                title="Groß-/Kleinschreibung beachten"
              >Aa</button>
              <button
                class="search-filter-btn"
                class:active={suchRegex}
                onclick={() => toggleSuchFilter("regex")}
                title="Regulärer Ausdruck"
              >.*</button>
            </div>
          </div>
          {#if buchSuchLaden}
            <div class="book-search-status"><i class="fa-solid fa-spinner fa-spin"></i> Suche...</div>
          {:else if buchSuchbegriff.length >= 2 && buchSuchTreffer.length === 0}
            <div class="book-search-status">Keine Treffer</div>
          {/if}
          {#if buchSuchTreffer.length > 0}
            <div class="book-search-count">
              {buchSuchGesamt} Treffer
              {#if buchSuchGesamt > buchSuchTreffer.length}
                <span class="search-count-hint">(zeige {buchSuchTreffer.length})</span>
              {/if}
            </div>
            <div class="book-search-results">
              {#each buchSuchTreffer as treffer, i (i)}
                <button
                  class="book-search-hit"
                  onclick={() => {
                    const q = encodeURIComponent(buchSuchbegriff);
                    if (book.file_format === "pdf") {
                      navigate(`/book/${book.id}/read?page=${treffer.seite}&q=${q}`);
                    } else {
                      navigate(`/book/${book.id}/read?percent=${treffer.prozent}&q=${q}`);
                    }
                  }}
                  title="Zur Stelle im Reader springen ({book.file_format === 'pdf' ? `Seite ${treffer.seite}` : `${treffer.prozent}%`})"
                >
                  <span class="hit-page">S. {treffer.seite}</span>
                  <span class="hit-kontext">{@html treffer.kontext}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    {#if aehnliche.vom_autor.length > 0 || aehnliche.in_kategorie.length > 0}
      <div class="similar-section">
        {#if aehnliche.vom_autor.length > 0}
          <h2 class="section-title">Vom selben Autor</h2>
          <div class="similar-grid">
            {#each aehnliche.vom_autor as b (b.id)}
              <a href="/book/{b.id}" class="similar-card">
                {#if b.cover_path}
                  <img src={coverUrl(b.id, b.updated_at)} alt="" class="similar-cover" onerror={(e) => e.target.style.display = 'none'} />
                {:else}
                  <div class="similar-cover-placeholder">
                    <span>{(b.file_format || "?").toUpperCase()}</span>
                  </div>
                {/if}
                <div class="similar-info">
                  <span class="similar-title">{b.title}</span>
                  {#if b.year}<span class="similar-year">{b.year}</span>{/if}
                </div>
              </a>
            {/each}
          </div>
        {/if}
        {#if aehnliche.in_kategorie.length > 0}
          <h2 class="section-title">In derselben Kategorie</h2>
          <div class="similar-grid">
            {#each aehnliche.in_kategorie as b (b.id)}
              <a href="/book/{b.id}" class="similar-card">
                {#if b.cover_path}
                  <img src={coverUrl(b.id, b.updated_at)} alt="" class="similar-cover" onerror={(e) => e.target.style.display = 'none'} />
                {:else}
                  <div class="similar-cover-placeholder">
                    <span>{(b.file_format || "?").toUpperCase()}</span>
                  </div>
                {/if}
                <div class="similar-info">
                  <span class="similar-title">{b.title}</span>
                  {#if b.author}<span class="similar-author">{b.author}</span>{/if}
                </div>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <AiCategorizeDialog
      bookId={book.id}
      open={aiDialogOpen}
      onClose={() => (aiDialogOpen = false)}
      onDone={() => ladeBuch(book.id)}
    />
  {/if}
</div>

<style>
  .book-detail {
    max-width: 960px;
    position: relative;
    z-index: 1;
  }

  .bg-cover-blur {
    position: fixed;
    inset: 0;
    z-index: 0;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    filter: blur(var(--cover-bg-blur)) saturate(var(--cover-bg-saturate));
    transform: scale(var(--cover-bg-scale));
    pointer-events: none;
  }

  .bg-cover-default {
    background-image: var(--cover-bg-default, linear-gradient(135deg, #1a1a2e 0%, #16213e 30%, #0f3460 60%, #533483 100%));
  }

  :global(:root:not(.dark)) .bg-cover-default {
    background-image: var(--cover-bg-default, linear-gradient(135deg, #667eea 0%, #764ba2 30%, #f093fb 60%, #4facfe 100%));
  }

  .bg-cover-overlay {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: var(--cover-bg-overlay);
  }

  :global(.grid-main:has(.book-detail)) {
    background: transparent !important;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .status-text {
    color: var(--color-text-muted);
    padding: 2rem 0;
  }

  .status-text.error {
    color: var(--color-error);
  }

  .detail-layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 2rem;
  }

  @media (max-width: 640px) {
    .detail-layout {
      grid-template-columns: 1fr;
    }
  }

  .cover-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .cover-wrapper {
    position: relative;
    border-radius: 8px;
    overflow: hidden;
  }

  .cover-overlay {
    position: absolute;
    inset: 0;
    background: var(--cover-hover-overlay);
    opacity: 0;
    transition: opacity 0.25s;
    pointer-events: none;
    border-radius: 8px;
  }

  .cover-wrapper:hover .cover-overlay {
    opacity: 1;
  }

  .cover-btn {
    position: absolute;
    pointer-events: auto;
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #fff;
    border-radius: 8px;
    font-size: 1rem;
    text-decoration: none;
    transition: background 0.15s, transform 0.15s;
  }

  .cover-btn:hover {
    background: rgba(255, 255, 255, 0.25);
    transform: scale(1.1);
  }

  .cover-btn-tl { top: 0.5rem; left: 0.5rem; }
  .cover-btn-tr { top: 0.5rem; right: 0.5rem; }
  .cover-btn-bl { bottom: 0.5rem; left: 0.5rem; }

  .weiterlesen-link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-accent);
    text-decoration: none;
    padding: 0.25rem 0;
  }

  .weiterlesen-link:hover {
    text-decoration: underline;
  }

  .cover-image {
    width: 100%;
    display: block;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }

  .cover-placeholder {
    aspect-ratio: 2 / 3;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    font-size: 2rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }


  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.625rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s;
  }

  .btn:hover {
    opacity: 0.9;
  }

  .btn-primary {
    background-color: var(--color-accent);
    color: #fff;
  }

  .btn-secondary {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
  }

  .btn-sm {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
  }

  .info-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 1.25rem;
  }

  .book-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
  }

  .book-authors {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.125rem;
    font-size: 1.125rem;
  }

  .author-link {
    color: var(--color-accent);
    text-decoration: none;
  }

  .author-link:hover {
    text-decoration: underline;
  }

  .author-sep {
    color: var(--color-text-muted);
    margin-right: 0.25rem;
  }

  .book-author {
    font-size: 1.125rem;
    color: var(--color-text-secondary);
  }

  .book-publisher {
    font-size: 0.875rem;
    color: var(--color-text-muted);
  }

  .rating-row {
    font-size: 1.25rem;
  }

  .action-groups {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .action-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.375rem;
  }

  .action-btn {
    padding: 0.5rem 0.25rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
    text-align: center;
  }

  .action-grid:first-child .action-btn {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    border-color: var(--glass-border-btn);
  }

  .action-grid:last-child .action-btn {
    background: var(--glass-bg-btn-alt);
    backdrop-filter: blur(var(--glass-blur-btn));
    border-style: dashed;
    border-color: var(--glass-border);
  }

  .action-btn:hover {
    background: rgba(0, 0, 0, 0.35);
  }

  .action-btn.active {
    border-color: var(--color-accent);
    color: var(--color-accent);
    background-color: var(--color-accent-light);
    border-style: solid;
  }

  .section-title {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    margin-bottom: 0.375rem;
  }

  .meta-section {
    padding-top: 0.5rem;
  }

  .buch-beschreibung {
    color: var(--color-text-secondary);
    line-height: 1.7;
    white-space: pre-line;
    margin: 0;
  }

  .tags-section {
    padding-top: 0.25rem;
  }

  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .chip {
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    text-decoration: none;
  }

  .chip:hover {
    background-color: var(--color-bg-tertiary);
  }

  .sammlung-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    background-color: color-mix(in srgb, var(--sammlung-color) 15%, transparent);
    color: var(--sammlung-color);
    border-color: color-mix(in srgb, var(--sammlung-color) 30%, transparent);
  }

  .sammlung-dot {
    width: 6px;
    height: 6px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .band-nr {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    opacity: 0.8;
  }

  .typ-chip {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-secondary);
    font-weight: 500;
  }

  /* Kategorien bearbeiten */
  .kat-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .kat-edit-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
  }

  .kat-edit-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .kat-edit-area {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .kat-chip-edit {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background-color: var(--color-bg-tertiary);
  }

  .kat-remove-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border: none;
    border-radius: 50%;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.5rem;
    cursor: pointer;
    padding: 0;
  }

  .kat-remove-btn:hover {
    background-color: color-mix(in srgb, var(--color-error) 15%, transparent);
    color: var(--color-error);
  }

  .kat-suche-wrap {
    position: relative;
  }

  .kat-suche-icon {
    position: absolute;
    left: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    pointer-events: none;
  }

  .kat-suche-input {
    width: 100%;
    padding: 0.375rem 0.5rem 0.375rem 1.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    outline: none;
  }

  .kat-suche-input:focus {
    border-color: var(--color-accent);
  }

  .kat-suche-input::placeholder {
    color: var(--color-text-muted);
  }

  .kat-ergebnisse {
    display: flex;
    flex-direction: column;
    gap: 1px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
    max-height: 200px;
    overflow-y: auto;
  }

  .kat-ergebnis {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.5rem;
    border: none;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    cursor: pointer;
    text-align: left;
  }

  .kat-ergebnis:hover {
    background-color: var(--color-accent-light);
  }

  .kat-plus-icon {
    font-size: 0.5625rem;
    color: var(--color-accent);
  }

  .kat-count {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    margin-left: auto;
  }

  .kat-leer {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-style: italic;
  }

  .position-section {
    padding-top: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }

  .position-details {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.25rem 0.75rem;
    margin-bottom: 0.75rem;
    padding: 0.625rem 0.75rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur-sm));
    border-radius: 8px;
    border: 1px solid var(--glass-border);
  }

  .pos-item {
    display: contents;
  }

  .pos-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .pos-value {
    font-size: 0.75rem;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    text-align: right;
    justify-self: end;
  }

  .pos-icon {
    display: flex;
    align-items: center;
  }

  .pos-papier {
    width: 18px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid var(--color-border);
  }

  .pos-papier-normal {
    background-color: #ffffff;
  }

  .pos-papier-sepia {
    background-color: #f4ecd8;
  }

  .pos-papier-dunkel {
    background-color: #1e1e1e;
  }

  .pos-papier-kontrast {
    background-color: #000000;
  }

  .pos-font-preview {
    font-size: 0.8125rem;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    display: inline-block;
  }

  /* Kategorien Toggle */
  .chip-toggle {
    background: none;
    border: 1px dashed var(--color-border);
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.75rem;
  }

  .chip-toggle:hover {
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  /* Metadaten-Anreicherung */
  .action-btn.loading {
    opacity: 0.6;
    cursor: wait;
  }

  .meta-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    padding: 0.25rem 0;
  }

  .meta-fehler {
    color: var(--color-error);
  }

  .meta-vergleich {
    padding: 0.75rem;
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }

  .meta-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .meta-header .section-title {
    margin: 0;
  }

  .meta-quelle {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    background-color: var(--color-bg-secondary);
    padding: 0.125rem 0.5rem;
    border-radius: 999px;
    border: 1px solid var(--color-border);
  }

  .vergleich-tabelle {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .vergleich-kopf {
    display: grid;
    grid-template-columns: 1.5rem 7rem 1fr 1fr;
    gap: 0.5rem;
    padding: 0.375rem 0;
    border-bottom: 1px solid var(--color-border);
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .vergleich-zeile {
    display: grid;
    grid-template-columns: 1.5rem 7rem 1fr 1fr;
    gap: 0.5rem;
    padding: 0.375rem 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    font-size: 0.8125rem;
    align-items: baseline;
    cursor: default;
  }

  .vergleich-zeile:last-child {
    border-bottom: none;
  }

  .vergleich-zeile.geaendert {
    background-color: color-mix(in srgb, var(--color-accent) 8%, transparent);
    margin: 0 -0.375rem;
    padding-left: 0.375rem;
    padding-right: 0.375rem;
    border-radius: 4px;
  }

  .vergleich-check {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .vergleich-check input[type="checkbox"] {
    cursor: pointer;
    accent-color: var(--color-accent);
  }

  .vergleich-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .vergleich-alt {
    color: var(--color-text-secondary);
    word-break: break-word;
  }

  .vergleich-alt.leer {
    color: var(--color-text-muted);
    font-style: italic;
  }

  .vergleich-neu {
    color: var(--color-text-primary);
    font-weight: 500;
    word-break: break-word;
  }

  .vergleich-neu.leer,
  .vergleich-neu.abgewaehlt {
    color: var(--color-text-muted);
    font-style: italic;
    font-weight: 400;
    opacity: 0.6;
  }

  .vergleich-neu.identisch {
    color: var(--color-text-muted);
    font-weight: 400;
  }

  .vergleich-zeile.ausgewaehlt {
    background: rgba(59, 130, 246, 0.08);
  }

  /* Cover-Vorschau */
  .cover-vorschau {
    height: 48px;
    border-radius: 3px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    object-fit: cover;
  }

  .cover-vorschau-wrap {
    position: relative;
    display: inline-block;
  }

  .cover-gross {
    display: none;
    position: absolute;
    bottom: calc(100% + 8px);
    left: 0;
    height: 240px;
    border-radius: 6px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    z-index: 20;
    pointer-events: none;
  }

  .cover-vorschau-wrap:hover .cover-gross {
    display: block;
  }

  .meta-kategorien {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    padding: 0.25rem 0;
  }

  .meta-kat-chip {
    padding: 0.125rem 0.5rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }

  .meta-kat-more {
    padding: 0.125rem 0.5rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Alle Daten (Rohdaten) */
  .raw-section {
    border-top: 1px solid var(--color-border);
    padding-top: 0.5rem;
  }

  .raw-toggle {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    background: none;
    border: none;
    color: var(--color-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.25rem 0;
  }

  .raw-toggle:hover {
    color: var(--color-accent);
  }

  .raw-liste {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .raw-eintrag {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .raw-key {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }

  .raw-value-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .raw-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .raw-chip {
    padding: 0.125rem 0.5rem;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }

  .raw-kat-check {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    cursor: pointer;
  }

  .raw-kat-check input[type="checkbox"] {
    accent-color: var(--color-accent);
    cursor: pointer;
  }

  .raw-kat-label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .raw-json {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-primary);
    padding: 0.375rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 200px;
    overflow-y: auto;
  }

  .raw-text {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    word-break: break-word;
  }

  .volltext-seiten-ctrl {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0;
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    flex-wrap: wrap;
  }

  .volltext-seite-input {
    width: 4rem;
    padding: 0.25rem 0.375rem;
    font-size: 0.8125rem;
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    border-radius: 0.25rem;
    text-align: center;
  }

  .volltext-seiten-info {
    color: var(--color-text-muted);
  }

  .volltext-vorschau {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.5rem 0;
  }

  .volltext-textarea {
    width: 100%;
    min-height: 300px;
    padding: 0.75rem;
    font-size: 0.875rem;
    line-height: 1.6;
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    resize: vertical;
    font-family: inherit;
  }

  .volltext-laden,
  .volltext-leer {
    padding: 0.5rem 0;
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  .meta-aktionen {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.25rem;
  }

  .notes-section {
    margin-top: 1.5rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 1rem;
  }

  /* Labels */
  .labels-section {
    margin-top: 1.5rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 1rem;
  }

  .labels-section .section-title {
    font-size: 0.875rem;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .labels-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .labels-scrollable {
    max-height: 220px;
    overflow-y: auto;
  }

  .label-item-wrap {
    border-radius: 4px;
  }

  .label-item-wrap:hover {
    background: var(--glass-placeholder);
  }

  .label-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.375rem;
  }

  .label-icon {
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .label-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    white-space: nowrap;
  }

  .label-page {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    font-size: 0.6875rem;
    font-family: inherit;
    color: var(--color-accent);
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
  }

  .label-page:hover {
    text-decoration: underline;
  }

  .label-expand {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.6875rem;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .label-expand.has-note,
  .label-item-wrap:hover .label-expand {
    opacity: 1;
  }

  .label-expand:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .label-note-edit {
    width: 100%;
    font-size: 0.8125rem;
    font-family: inherit;
    color: var(--color-text-secondary);
    background: color-mix(in srgb, var(--color-bg-primary) 30%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border) 40%, transparent);
    border-radius: 4px;
    padding: 0.375rem 0.5rem;
    line-height: 1.5;
    resize: vertical;
    box-sizing: border-box;
  }

  .label-note-edit:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .label-snippet {
    flex: 1;
    min-width: 0;
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-style: italic;
  }

  .label-edit-fields {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    margin: 0.25rem 0.375rem 0.375rem 1.625rem;
    width: calc(100% - 2rem);
  }

  .label-name-edit {
    width: 100%;
    border: 1px solid color-mix(in srgb, var(--color-border) 40%, transparent);
    background: color-mix(in srgb, var(--color-bg-primary) 30%, transparent);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: inherit;
    border-radius: 4px;
    padding: 0.25rem 0.375rem;
    outline: none;
    box-sizing: border-box;
  }

  .label-name-edit:focus {
    border-color: var(--color-accent);
  }

  .label-name-edit::placeholder {
    color: var(--color-text-muted);
  }

  .label-text-snippet {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-style: italic;
    line-height: 1.4;
    padding: 0.25rem 0.375rem;
    background: color-mix(in srgb, var(--color-bg-primary) 20%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border) 20%, transparent);
    border-radius: 4px;
    max-height: 4em;
    overflow: hidden;
  }

  .label-delete {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.6875rem;
    flex-shrink: 0;
    opacity: 0;
    transition: opacity 0.15s;
    margin-left: auto;
  }

  .label-item-wrap:hover .label-delete {
    opacity: 1;
  }

  .label-delete:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-error);
  }

  /* Buch-Volltextsuche */
  .book-search-section {
    margin-top: 1.5rem;
  }

  .book-search-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.625rem 0.75rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur-sm));
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .book-search-toggle:hover {
    background-color: var(--color-bg-secondary);
  }

  .book-search-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .book-search-row {
    display: flex;
    gap: 0.375rem;
    align-items: center;
  }

  .book-search-input {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: var(--glass-placeholder);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-family: inherit;
    min-width: 0;
  }

  .book-search-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .book-search-filters {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
  }

  .search-filter-btn {
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--glass-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    font-weight: 600;
    line-height: 1;
  }

  .search-filter-btn:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .search-filter-btn.active {
    background: var(--color-accent-light);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .book-search-status {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    padding: 0.25rem 0;
  }

  .book-search-count {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-weight: 500;
  }

  .search-count-hint {
    opacity: 0.6;
    font-weight: 400;
  }

  .book-search-results {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    max-height: 40rem;
    overflow-y: auto;
  }

  .book-search-hit {
    display: flex;
    width: 100%;
    gap: 0.75rem;
    padding: 0.5rem 0.625rem;
    background: var(--glass-placeholder);
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    text-decoration: none;
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: inherit;
    line-height: 1.4;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s;
  }

  .book-search-hit:hover {
    background: var(--glass-bg-btn-alt);
  }

  .hit-page {
    flex-shrink: 0;
    font-weight: 600;
    color: var(--color-accent);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    min-width: 3rem;
  }

  .hit-kontext {
    color: var(--color-text-secondary);
    word-break: break-word;
  }

  .hit-kontext :global(mark) {
    background-color: var(--color-warning);
    color: #000;
    border-radius: 2px;
    padding: 0 0.125rem;
  }

  .similar-section {
    margin-top: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 1rem;
  }

  .similar-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .similar-card {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    text-decoration: none;
    color: var(--color-text-primary);
    border-radius: 6px;
    transition: transform 0.15s;
  }

  .similar-card:hover {
    transform: translateY(-2px);
  }

  .similar-cover {
    width: 100%;
    aspect-ratio: 2 / 3;
    object-fit: cover;
    border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
  }

  .similar-cover-placeholder {
    width: 100%;
    aspect-ratio: 2 / 3;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
  }

  .similar-info {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .similar-title {
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .similar-author,
  .similar-year {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Editiermodus */
  .edit-form {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .edit-field {
    display: flex;
    flex-direction: column;
    gap: 0.1875rem;
    flex: 1;
  }

  .edit-label {
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }

  .edit-input {
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-family: inherit;
    width: 100%;
  }

  .edit-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .edit-input.mono {
    font-family: var(--font-mono);
  }

  .edit-textarea {
    resize: vertical;
    min-height: 3rem;
  }

  .edit-row {
    display: flex;
    gap: 0.75rem;
  }

  .edit-isbn-row {
    display: flex;
    gap: 0.25rem;
  }

  .edit-isbn-row .edit-input {
    flex: 1;
  }

  .edit-aktionen {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  /* ISBN-Scan */
  .isbn-scan-ergebnis {
    padding: 0.5rem;
    background-color: var(--color-bg-tertiary);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .isbn-scan-titel {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .isbn-scan-leer {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    font-style: italic;
  }

  .isbn-scan-gruppe {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
  }

  .isbn-chip {
    padding: 0.1875rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .isbn-chip:hover {
    border-color: var(--color-accent);
    background-color: color-mix(in srgb, var(--color-accent) 10%, transparent);
  }
</style>
