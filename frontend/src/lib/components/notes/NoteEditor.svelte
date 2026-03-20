<script>
  let {
    initialContent = "",
    pageRef = "",
    onSave = () => {},
    onCancel = null,
  } = $props();

  let content = $state(initialContent);
  let pageReference = $state(pageRef);
</script>

<div class="note-editor">
  <textarea
    class="note-textarea"
    placeholder="Notiz schreiben..."
    bind:value={content}
    rows="4"
  ></textarea>
  <div class="editor-footer">
    <input
      type="text"
      class="page-input"
      placeholder="Seite (optional)"
      bind:value={pageReference}
    />
    <div class="editor-actions">
      {#if onCancel}
        <button class="btn btn-secondary" onclick={onCancel}>
          Abbrechen
        </button>
      {/if}
      <button
        class="btn btn-primary"
        disabled={!content.trim()}
        onclick={() => onSave({ content: content.trim(), page_reference: pageReference || null })}
      >
        Speichern
      </button>
    </div>
  </div>
</div>

<style>
  .note-editor {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .note-textarea {
    width: 100%;
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
    resize: vertical;
    min-height: 80px;
  }

  .note-textarea:focus {
    outline: 2px solid var(--color-accent);
    outline-offset: -1px;
  }

  .editor-footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .page-input {
    width: 120px;
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
  }

  .editor-actions {
    display: flex;
    gap: 0.375rem;
    margin-left: auto;
  }

  .btn {
    padding: 0.375rem 0.75rem;
    border-radius: 6px;
    font-size: 0.8125rem;
    cursor: pointer;
    border: none;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: default;
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
</style>
