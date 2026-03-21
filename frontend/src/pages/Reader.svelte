<script>
  import { navigate } from "../lib/router.svelte.js";
  import { holeBuch } from "../lib/api/books.js";
  import { ui } from "../lib/stores/ui.svelte.js";
  import { onDestroy } from "svelte";
  import PdfReader from "../lib/components/reader/PdfReader.svelte";
  import EpubReader from "../lib/components/reader/EpubReader.svelte";
  import MarkdownReader from "../lib/components/reader/MarkdownReader.svelte";

  let { params } = $props();

  // Beim Verlassen des Readers Fullscreen deaktivieren
  onDestroy(() => {
    ui.readerFullscreen = false;
  });

  let book = $state(null);
  let laden = $state(true);
  let fehler = $state(null);

  // URL-Parameter auslesen
  function getUrlParams() {
    const sp = new URLSearchParams(window.location.search || "");
    return {
      page: Number(sp.get("page")) || 0,
      zoom: Number(sp.get("zoom")) || 0,
      ansicht: sp.get("ansicht") || "",
      papier: sp.get("papier") || "",
      cfi: sp.get("cfi") || "",
    };
  }

  let urlParams = getUrlParams();

  // Gespeicherte Reader-Settings aus reading_position parsen
  function parseGespeicherteSettings(pos) {
    if (!pos) return {};
    // JSON-Formate: "pdf:{...}", "epub:{...}", "txt:50"
    for (const prefix of ["pdf:", "epub:"]) {
      if (pos.startsWith(prefix)) {
        try {
          return JSON.parse(pos.slice(prefix.length));
        } catch { return {}; }
      }
    }
    if (pos.startsWith("txt:")) {
      // Neues JSON-Format oder altes Zahl-Format
      const rest = pos.slice(4);
      if (rest.startsWith("{")) {
        try { return JSON.parse(rest); } catch { return {}; }
      }
      return { scrollPct: Number(rest) || 0 };
    }
    // Altes Format: "cfi:..." oder "page:42"
    if (pos.startsWith("cfi:")) {
      return { cfi: pos.slice(4) };
    }
    const match = pos.match(/page:(\d+)/);
    if (match) return { page: Number(match[1]) };
    return {};
  }

  $effect(() => {
    ladeBuch(Number(params.id));
  });

  async function ladeBuch(id) {
    laden = true;
    fehler = null;
    try {
      book = await holeBuch(id);
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }

  // Gespeicherte Settings (URL > DB > Defaults)
  let saved = $derived(parseGespeicherteSettings(book?.reading_position));

  let initialPage = $derived(urlParams.page > 0 ? urlParams.page : (saved.page || 1));
  let initialAnsicht = $derived(urlParams.ansicht || saved.ansicht || "");
  let initialPapier = $derived(urlParams.papier || saved.papier || "");
  let initialZoom = $derived(urlParams.zoom > 0 ? urlParams.zoom : (saved.zoom || 0));

  let initialCfi = $derived(urlParams.cfi || saved.cfi || "");

  function goBack() {
    navigate(`/book/${params.id}`);
  }
</script>

<div class="reader-page">
  {#if laden}
    <div class="status">Buch wird geladen...</div>
  {:else if fehler}
    <div class="status error">
      Fehler: {fehler}
      <a href="/book/{params.id}">Zurück zum Buch</a>
    </div>
  {:else if book}
    {#if book.file_format === "pdf"}
      <PdfReader
        bookId={book.id}
        title={book.title}
        {initialPage}
        {initialAnsicht}
        {initialPapier}
        {initialZoom}
        onBack={goBack}
      />
    {:else if book.file_format === "epub" || book.file_format === "mobi"}
      <EpubReader
        bookId={book.id}
        title={book.title}
        {initialCfi}
        {initialPapier}
        initialFontSize={saved.fontSize || 0}
        initialFontFamily={saved.fontFamily || ""}
        initialLineHeight={saved.lineHeight || 0}
        initialFgColor={saved.fgColor || ""}
        initialBgColor={saved.bgColor || ""}
        initialMaxWidthSingle={saved.maxWidthSingle || 0}
        initialMaxWidthDouble={saved.maxWidthDouble || 0}
        initialSinglePage={saved.singlePage || false}
        onBack={goBack}
      />
    {:else if book.file_format === "txt" || book.file_format === "md"}
      <MarkdownReader
        bookId={book.id}
        title={book.title}
        {initialPapier}
        initialFontSize={saved.fontSize || 0}
        initialScrollPct={saved.scrollPct || 0}
        onBack={goBack}
      />
    {:else}
      <div class="status">
        Format "{book.file_format}" wird nicht unterstützt.
      </div>
    {/if}
  {/if}
</div>

<style>
  .reader-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    margin: -1.5rem;
  }

  .status {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 1rem;
    color: var(--color-text-muted);
  }

  .status.error {
    color: var(--color-error);
  }

  .status a {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }
</style>
