<script>
  import NoteEditor from "./NoteEditor.svelte";
  import { notizenFuerBuch, erstelleNotiz, loescheNotiz } from "../../api/notes.js";
  import { navigate } from "../../router.svelte.js";

  let { bookId } = $props();

  let notizen = $state([]);
  let laden = $state(true);
  let showEditor = $state(false);

  $effect(() => {
    ladeNotizen(bookId);
  });

  async function ladeNotizen(id) {
    laden = true;
    try {
      notizen = await notizenFuerBuch(id);
    } catch {
      notizen = [];
    } finally {
      laden = false;
    }
  }

  async function onSave(data) {
    try {
      const notiz = await erstelleNotiz(bookId, data);
      notizen = [notiz, ...notizen];
      showEditor = false;
    } catch { /* still */ }
  }

  async function onDelete(noteId) {
    try {
      await loescheNotiz(noteId);
      notizen = notizen.filter((n) => n.id !== noteId);
    } catch { /* still */ }
  }

  function formatDate(dateStr) {
    if (!dateStr) return "";
    return new Date(dateStr).toLocaleDateString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
</script>

<div class="note-list">
  <div class="list-header">
    <h3 class="section-title">Notizen ({notizen.length})</h3>
    <button
      class="add-btn"
      onclick={() => (showEditor = !showEditor)}
    >
      {#if showEditor}
        Abbrechen
      {:else}
        <i class="fa-solid fa-plus"></i> Notiz
      {/if}
    </button>
  </div>

  {#if showEditor}
    <NoteEditor {onSave} onCancel={() => (showEditor = false)} />
  {/if}

  {#if laden}
    <p class="info">Wird geladen...</p>
  {:else if notizen.length === 0 && !showEditor}
    <p class="info">Noch keine Notizen vorhanden.</p>
  {:else}
    {#each notizen as notiz (notiz.id)}
      <div class="note-item">
        <div class="note-content">{notiz.content}</div>
        <div class="note-footer">
          <span class="note-date">{formatDate(notiz.updated_at || notiz.created_at)}</span>
          {#if notiz.page_reference || notiz.cfi_reference}
            <button
              class="note-jump"
              onclick={() => {
                const params = new URLSearchParams();
                if (notiz.cfi_reference) params.set("cfi", notiz.cfi_reference);
                else if (notiz.page_reference && notiz.page_reference.includes("%")) params.set("percent", notiz.page_reference.replace("%", ""));
                else if (notiz.page_reference) params.set("page", notiz.page_reference);
                navigate(`/book/${bookId}/read${params.toString() ? "?" + params.toString() : ""}`);
              }}
              title="Im Reader öffnen"
            >
              <i class="fa-solid fa-arrow-up-right-from-square"></i>
              {notiz.page_reference || "Zur Stelle"}
            </button>
          {/if}
          <button
            class="delete-btn"
            onclick={() => onDelete(notiz.id)}
            title="Notiz löschen"
          >
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
      </div>
    {/each}
  {/if}
</div>

<style>
  .note-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .list-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .section-title {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .add-btn {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.25rem 0.625rem;
    font-size: 0.75rem;
    color: var(--color-accent);
    cursor: pointer;
  }

  .info {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .note-item {
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  .note-content {
    font-size: 0.875rem;
    color: var(--color-text-primary);
    line-height: 1.5;
    white-space: pre-wrap;
  }

  .note-footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .note-jump {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background-color: var(--color-bg-tertiary);
    padding: 0.0625rem 0.375rem;
    border-radius: 4px;
    border: none;
    color: var(--color-accent);
    font-size: 0.6875rem;
    font-family: inherit;
    cursor: pointer;
  }

  .note-jump:hover {
    background-color: color-mix(in srgb, var(--color-accent) 15%, transparent);
    text-decoration: underline;
  }

  .delete-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    margin-left: auto;
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.6875rem;
    flex-shrink: 0;
  }

  .delete-btn:hover {
    color: var(--color-error);
  }
</style>
