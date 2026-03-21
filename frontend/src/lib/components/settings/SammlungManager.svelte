<script>
  import { sammlungenStore } from "../../stores/tags.svelte.js";
  import { erstelleSammlung, aktualisiereSammlung, loescheSammlung } from "../../api/collections.js";
  import ColorPicker from "../ui/ColorPicker.svelte";
  import { onMount } from "svelte";

  let editing = $state(null);
  let showForm = $state(false);
  let formData = $state({ name: "", description: "", color: "#2563eb" });
  let saving = $state(false);
  let confirmDeleteId = $state(null);

  let sammlungen = $derived(sammlungenStore.sammlungen);

  function startCreate() {
    editing = null;
    formData = { name: "", description: "", color: "#2563eb" };
    showForm = true;
  }

  function startEdit(s) {
    editing = s;
    formData = {
      name: s.name,
      description: s.description || "",
      color: s.color || "#2563eb",
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
        await aktualisiereSammlung(editing.id, formData);
      } else {
        await erstelleSammlung(formData);
      }
      await sammlungenStore.aktualisieren();
      showForm = false;
      editing = null;
    } catch (e) {
      console.error("Sammlung speichern fehlgeschlagen:", e);
    } finally {
      saving = false;
    }
  }

  async function deleteSammlung(id) {
    try {
      await loescheSammlung(id);
      await sammlungenStore.aktualisieren();
      confirmDeleteId = null;
    } catch (e) {
      console.error("Sammlung löschen fehlgeschlagen:", e);
    }
  }

  onMount(() => {
    sammlungenStore.aktualisieren();
  });
</script>

<div class="mgr">
  <div class="mgr-head">
    <span class="mgr-title">
      <i class="fa-solid fa-layer-group"></i> Sammlungen
      {#if sammlungen.length}<span class="badge">{sammlungen.length}</span>{/if}
    </span>
    <button class="btn-add" onclick={startCreate}>
      <i class="fa-solid fa-plus"></i> Neu
    </button>
  </div>

  <p class="mgr-desc">
    Sammlungen gruppieren Bücher zu Reihen oder Serien (z.B. Perry Rhodan, Spiegel-Bestseller).
    Jedes Buch kann genau einer Sammlung zugeordnet werden, mit optionaler Bandnummer.
  </p>

  {#if showForm}
    <div class="form">
      <div class="form-row">
        <input
          type="text"
          class="form-input flex-1"
          bind:value={formData.name}
          placeholder="Sammlungsname..."
        />
        <ColorPicker value={formData.color} onchange={(c) => (formData.color = c)} />
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
      <div class="form-row mt">
        <input
          type="text"
          class="form-input flex-1"
          bind:value={formData.description}
          placeholder="Beschreibung (optional)..."
        />
      </div>
    </div>
  {/if}

  <div class="list">
    {#each sammlungen as s (s.id)}
      <div class="row">
        <span class="dot" style="background-color: {s.color || '#2563eb'}"></span>
        <span class="row-name">{s.name}</span>
        {#if s.description}
          <span class="row-desc">{s.description}</span>
        {/if}
        {#if s.buch_anzahl}
          <span class="row-count">{s.buch_anzahl}</span>
        {/if}
        <div class="row-actions">
          <button class="act" onclick={() => startEdit(s)} title="Bearbeiten">
            <i class="fa-solid fa-pen"></i>
          </button>
          {#if confirmDeleteId === s.id}
            <button class="act danger" onclick={() => deleteSammlung(s.id)} title="Wirklich löschen">
              <i class="fa-solid fa-check"></i>
            </button>
            <button class="act" onclick={() => (confirmDeleteId = null)}>
              <i class="fa-solid fa-xmark"></i>
            </button>
          {:else}
            <button class="act danger" onclick={() => (confirmDeleteId = s.id)} title="Löschen">
              <i class="fa-solid fa-trash"></i>
            </button>
          {/if}
        </div>
      </div>
    {/each}
    {#if sammlungen.length === 0}
      <div class="empty">Noch keine Sammlungen erstellt.</div>
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
    position: sticky;
    top: 0;
    z-index: 5;
    background-color: var(--color-bg-primary);
    padding: 0.5rem 0;
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

  .mgr-desc {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
  }

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

  .form-row.mt { margin-top: 0.375rem; }

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

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .row-name {
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .row-desc {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
