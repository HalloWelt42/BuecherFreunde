<script>
  import { tagsStore } from "../../stores/tags.svelte.js";
  import { erstelleTag, aktualisiereTag, loescheTag } from "../../api/tags.js";
  import ColorPicker from "../ui/ColorPicker.svelte";
  import IconPicker from "../ui/IconPicker.svelte";
  import { onMount } from "svelte";

  let editing = $state(null);
  let showForm = $state(false);
  let formData = $state({ name: "", color: "#6b7280", icon: "" });
  let saving = $state(false);
  let confirmDeleteId = $state(null);

  let tags = $derived(tagsStore.tags.map(t => ({
    ...t,
    isAi: t.name?.startsWith("ai_"),
  })));

  function startCreate() {
    editing = null;
    formData = { name: "", color: "#6b7280", icon: "" };
    showForm = true;
  }

  function startEdit(tag) {
    editing = tag;
    formData = {
      name: tag.name,
      color: tag.color || "#6b7280",
      icon: tag.icon || "",
    };
    showForm = true;
  }

  function cancelForm() {
    showForm = false;
    editing = null;
  }

  async function save() {
    if (!formData.name.trim()) return;
    saving = true;
    try {
      if (editing) {
        await aktualisiereTag(editing.id, formData);
      } else {
        await erstelleTag(formData);
      }
      await tagsStore.aktualisieren();
      showForm = false;
      editing = null;
    } catch (e) {
      console.error("Tag speichern fehlgeschlagen:", e);
    } finally {
      saving = false;
    }
  }

  async function deleteTag(id) {
    try {
      await loescheTag(id);
      await tagsStore.aktualisieren();
      confirmDeleteId = null;
    } catch (e) {
      console.error("Tag loeschen fehlgeschlagen:", e);
    }
  }

  onMount(() => {
    tagsStore.aktualisieren();
  });
</script>

<div class="mgr">
  <div class="mgr-head">
    <span class="mgr-title">
      <i class="fa-solid fa-tags"></i> Tags
      {#if tags.length}<span class="badge">{tags.length}</span>{/if}
    </span>
    <button class="btn-add" onclick={startCreate}>
      <i class="fa-solid fa-plus"></i> Neu
    </button>
  </div>

  {#if showForm}
    <div class="form">
      <div class="form-row">
        <input
          type="text"
          class="form-input flex-1"
          bind:value={formData.name}
          placeholder="Tagname..."
        />
        <ColorPicker value={formData.color} onchange={(c) => (formData.color = c)} />
        <IconPicker value={formData.icon} onchange={(i) => (formData.icon = i)} />
        <div class="form-btns">
          <button class="btn-save" onclick={save} disabled={saving || !formData.name.trim()}>
            {#if saving}<i class="fa-solid fa-spinner fa-spin"></i>{:else}<i class="fa-solid fa-check"></i>{/if}
            {editing ? "Speichern" : "Erstellen"}
          </button>
          <button class="btn-cancel" onclick={cancelForm}>
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </div>
    </div>
  {/if}

  <div class="list">
    {#each tags as tag (tag.id)}
      <div class="row" class:ai={tag.isAi}>
        <span class="dot" style="background-color: {tag.color || '#6b7280'}"></span>
        {#if tag.icon}
          <i class="fa-solid {tag.icon} row-icon" style="color: {tag.color || '#6b7280'}"></i>
        {/if}
        <span class="row-name">
          {tag.name}
          {#if tag.isAi}<span class="ai-badge">KI</span>{/if}
        </span>
        {#if tag.buch_anzahl}
          <span class="row-count">{tag.buch_anzahl}</span>
        {/if}
        <div class="row-actions">
          <button class="act" onclick={() => startEdit(tag)} title="Bearbeiten">
            <i class="fa-solid fa-pen"></i>
          </button>
          {#if confirmDeleteId === tag.id}
            <button class="act danger" onclick={() => deleteTag(tag.id)} title="Wirklich loeschen">
              <i class="fa-solid fa-check"></i>
            </button>
            <button class="act" onclick={() => (confirmDeleteId = null)}>
              <i class="fa-solid fa-xmark"></i>
            </button>
          {:else}
            <button class="act danger" onclick={() => (confirmDeleteId = tag.id)} title="Loeschen">
              <i class="fa-solid fa-trash"></i>
            </button>
          {/if}
        </div>
      </div>
    {/each}
    {#if tags.length === 0}
      <div class="empty">Noch keine Tags erstellt.</div>
    {/if}
  </div>
</div>

<style>
  .mgr {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .mgr-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .mgr-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .mgr-title i { color: var(--color-accent); }

  .badge {
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.3125rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    border: none;
    border-radius: 5px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.6875rem;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-add:hover { opacity: 0.9; }

  .form {
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
  }

  .form-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .form-input {
    padding: 0.3125rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-sans);
  }

  .form-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .flex-1 { flex: 1; min-width: 100px; }

  .form-btns {
    display: flex;
    gap: 0.25rem;
    margin-left: auto;
  }

  .btn-save {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    border: none;
    border-radius: 5px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.6875rem;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-save:disabled { opacity: 0.5; cursor: default; }

  .btn-cancel {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
  }

  .btn-cancel:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    overflow: hidden;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    border-bottom: 1px solid var(--color-border);
    transition: background-color 0.06s;
    font-size: 0.8125rem;
  }

  .row:last-child { border-bottom: none; }
  .row:hover { background-color: var(--color-bg-tertiary); }

  .row.ai {
    border-left: 2px solid var(--color-accent);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .row-icon {
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .row-name {
    font-weight: 500;
    color: var(--color-text-primary);
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .ai-badge {
    font-size: 0.5rem;
    font-weight: 700;
    padding: 0.0625rem 0.25rem;
    border-radius: 3px;
    background-color: var(--color-accent-light);
    color: var(--color-accent);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .row-count {
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .row-actions {
    display: flex;
    gap: 0.125rem;
    margin-left: auto;
    opacity: 0;
    transition: opacity 0.08s;
  }

  .row:hover .row-actions { opacity: 1; }

  .act {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.375rem;
    height: 1.375rem;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.5625rem;
    cursor: pointer;
  }

  .act:hover {
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
  }

  .act.danger:hover { color: var(--color-error); }

  .empty {
    padding: 1.5rem;
    text-align: center;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
