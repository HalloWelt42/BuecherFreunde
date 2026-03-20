<script>
  import { dateiUrl } from "../../api/books.js";
  import { getToken } from "../../api/client.js";

  let { bookId } = $props();

  let content = $state("");
  let laden = $state(true);
  let fehler = $state(null);

  $effect(() => {
    ladeText(bookId);
  });

  async function ladeText(id) {
    laden = true;
    fehler = null;
    try {
      const url = dateiUrl(id);
      const response = await fetch(url, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error("Datei konnte nicht geladen werden");
      content = await response.text();
    } catch (e) {
      fehler = e.message;
    } finally {
      laden = false;
    }
  }
</script>

<div class="markdown-reader">
  {#if laden}
    <div class="status">Text wird geladen...</div>
  {:else if fehler}
    <div class="status error">{fehler}</div>
  {:else}
    <div class="text-content">
      <pre class="text-pre">{content}</pre>
    </div>
  {/if}
</div>

<style>
  .markdown-reader {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .status {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--color-text-muted);
  }

  .status.error {
    color: var(--color-error);
  }

  .text-content {
    flex: 1;
    overflow: auto;
    padding: 2rem;
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
  }

  .text-pre {
    font-family: var(--font-sans);
    font-size: 1rem;
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: var(--color-text-primary);
  }
</style>
