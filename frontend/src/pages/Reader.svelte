<script>
  import { navigate } from "../lib/router.svelte.js";
  import { holeBuch } from "../lib/api/books.js";
  import ReaderToolbar from "../lib/components/reader/ReaderToolbar.svelte";
  import PdfReader from "../lib/components/reader/PdfReader.svelte";
  import EpubReader from "../lib/components/reader/EpubReader.svelte";
  import MarkdownReader from "../lib/components/reader/MarkdownReader.svelte";

  let { params } = $props();

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
    if (pos.startsWith("pdf:")) {
      try {
        return JSON.parse(pos.slice(4));
      } catch { return {}; }
    }
    // Altes Format: "page:42"
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

  let initialCfi = $derived.by(() => {
    if (urlParams.cfi) return urlParams.cfi;
    if (book?.reading_position?.startsWith("cfi:")) {
      return book.reading_position.slice(4);
    }
    return "";
  });

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
    <ReaderToolbar bookId={book.id} title={book.title} onBack={goBack} />

    {#if book.file_format === "pdf"}
      <PdfReader
        bookId={book.id}
        {initialPage}
        {initialAnsicht}
        {initialPapier}
        {initialZoom}
      />
    {:else if book.file_format === "epub" || book.file_format === "mobi"}
      <EpubReader bookId={book.id} {initialCfi} />
    {:else if book.file_format === "txt" || book.file_format === "md"}
      <MarkdownReader bookId={book.id} />
    {:else}
      <div class="status">
        Format "{book.file_format}" wird nicht unterstützt.
        <a href="/api/books/{book.id}/file" download>Datei herunterladen</a>
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
