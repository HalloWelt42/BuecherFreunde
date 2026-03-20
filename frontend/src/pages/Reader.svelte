<script>
  import { router, push } from "svelte-spa-router";
  import { holeBuch } from "../lib/api/books.js";
  import ReaderToolbar from "../lib/components/reader/ReaderToolbar.svelte";
  import PdfReader from "../lib/components/reader/PdfReader.svelte";
  import EpubReader from "../lib/components/reader/EpubReader.svelte";
  import MarkdownReader from "../lib/components/reader/MarkdownReader.svelte";

  let { params } = $props();

  let book = $state(null);
  let laden = $state(true);
  let fehler = $state(null);

  let initialPage = $derived.by(() => {
    const qs = new URLSearchParams(router.querystring || "");
    return Number(qs.get("page")) || 1;
  });

  let initialCfi = $derived.by(() => {
    const qs = new URLSearchParams(router.querystring || "");
    return qs.get("cfi") || "";
  });

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

  function goBack() {
    push(`/book/${params.id}`);
  }
</script>

<div class="reader-page">
  {#if laden}
    <div class="status">Buch wird geladen...</div>
  {:else if fehler}
    <div class="status error">
      Fehler: {fehler}
      <a href="#/book/{params.id}">Zurück zum Buch</a>
    </div>
  {:else if book}
    <ReaderToolbar bookId={book.id} title={book.title} onBack={goBack} />

    {#if book.file_format === "pdf"}
      <PdfReader bookId={book.id} {initialPage} />
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
    height: calc(100vh - var(--header-height) - 2rem);
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
