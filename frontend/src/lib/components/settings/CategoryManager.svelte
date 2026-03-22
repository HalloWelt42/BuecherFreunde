<script>
  import { categoriesStore } from "../../stores/categories.svelte.js";
  import { erstelleKategorie, aktualisiereKategorie, loescheKategorie } from "../../api/categories.js";
  import ColorPicker from "../ui/ColorPicker.svelte";
  import IconPicker from "../ui/IconPicker.svelte";
  import { onMount } from "svelte";

  let editing = $state(null);
  let showForm = $state(false);
  let formData = $state({ name: "", description: "", color: "#6b7280", icon: "", spezial: false });
  let saving = $state(false);
  let confirmDeleteId = $state(null);

  let cats = $derived(categoriesStore.kategorien.map(c => ({
    ...c,
    isAi: c.name?.startsWith("ai_"),
  })));

  function startCreate() {
    editing = null;
    formData = { name: "", description: "", color: "#6b7280", icon: "", spezial: false };
    showForm = true;
  }

  function startEdit(cat) {
    editing = cat;
    formData = {
      name: cat.name,
      description: cat.description || "",
      color: cat.color || "#6b7280",
      icon: cat.icon || "",
      spezial: !!cat.spezial,
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
        await aktualisiereKategorie(editing.id, { ...formData, parent_id: null });
      } else {
        await erstelleKategorie({ ...formData, parent_id: null });
      }
      await categoriesStore.aktualisieren();
      showForm = false;
      editing = null;
    } catch (e) {
      console.error("Kategorie speichern fehlgeschlagen:", e);
    } finally {
      saving = false;
    }
  }

  async function toggleSpezial(cat) {
    try {
      await aktualisiereKategorie(cat.id, { spezial: !cat.spezial });
      await categoriesStore.aktualisieren();
    } catch (e) {
      console.error("Spezial-Toggle fehlgeschlagen:", e);
    }
  }

  async function deleteCategory(id) {
    try {
      await loescheKategorie(id);
      await categoriesStore.aktualisieren();
      confirmDeleteId = null;
    } catch (e) {
      console.error("Kategorie löschen fehlgeschlagen:", e);
    }
  }

  onMount(() => {
    categoriesStore.aktualisieren();
  });
</script>

<div class="mgr">
  <div class="mgr-head">
    <span class="mgr-title">
      <i class="fa-solid fa-folder"></i> Kategorien
      {#if cats.length}<span class="badge">{cats.length}</span>{/if}
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
          placeholder="Name..."
        />
        <input
          type="text"
          class="form-input flex-2"
          bind:value={formData.description}
          placeholder="Beschreibung (optional)..."
        />
      </div>
      <div class="form-row">
        <ColorPicker value={formData.color} onchange={(c) => (formData.color = c)} />
        <IconPicker value={formData.icon} onchange={(i) => (formData.icon = i)} />
        <label class="spezial-toggle">
          <input type="checkbox" bind:checked={formData.spezial} />
          <span>Spezialkategorie</span>
        </label>
        <div class="form-btns">
          <button class="btn-save" onclick={save} disabled={saving || !formData.name.trim()}>
            {#if saving}<i class="fa-solid fa-spinner fa-spin"></i>{:else}<i class="fa-solid fa-check"></i>{/if}
            {editing ? "Speichern" : "Erstellen"}
          </button>
          <button class="btn-cancel" onclick={cancelForm} aria-label="Abbrechen">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </div>
    </div>
  {/if}

  <div class="list">
    {#each cats as cat (cat.id)}
      <div class="row" class:ai={cat.isAi}>
        <span class="dot" style="background-color: {cat.color || '#6b7280'}"></span>
        {#if cat.icon}
          <i class="fa-solid {cat.icon} row-icon" style="color: {cat.color || '#6b7280'}"></i>
        {/if}
        <span class="row-name">
          {cat.name}
          {#if cat.isAi}<span class="ai-badge">KI</span>{/if}
          {#if cat.spezial}<span class="spezial-badge">Menü</span>{/if}
        </span>
        {#if cat.description}
          <span class="row-desc">{cat.description}</span>
        {/if}
        {#if cat.buch_anzahl}
          <span class="row-count">{cat.buch_anzahl}</span>
        {/if}
        <div class="row-actions">
          <button
            class="act"
            class:spezial-active={cat.spezial}
            onclick={() => toggleSpezial(cat)}
            title={cat.spezial ? "Aus Sidebar entfernen" : "In Sidebar anzeigen"}
          >
            <i class="fa-solid fa-bars"></i>
          </button>
          <button class="act" onclick={() => startEdit(cat)} title="Bearbeiten">
            <i class="fa-solid fa-pen"></i>
          </button>
          {#if confirmDeleteId === cat.id}
            <button class="act danger" onclick={() => deleteCategory(cat.id)} title="Wirklich löschen">
              <i class="fa-solid fa-check"></i>
            </button>
            <button class="act" onclick={() => (confirmDeleteId = null)} aria-label="Abbrechen">
              <i class="fa-solid fa-xmark"></i>
            </button>
          {:else}
            <button class="act danger" onclick={() => (confirmDeleteId = cat.id)} title="Löschen">
              <i class="fa-solid fa-trash"></i>
            </button>
          {/if}
        </div>
      </div>
    {/each}
    {#if cats.length === 0}
      <div class="empty">Noch keine Kategorien erstellt.</div>
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
    z-index: 10;
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

  /* Formular */
  .form {
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
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
  .flex-2 { flex: 2; min-width: 140px; }

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

  /* Liste */
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
    border-radius: 3px;
    flex-shrink: 0;
  }

  .row-icon {
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .row-name {
    font-weight: 500;
    color: var(--color-text-primary);
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

  .spezial-toggle {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    cursor: pointer;
    user-select: none;
  }

  .spezial-toggle input {
    width: 0.875rem;
    height: 0.875rem;
    accent-color: var(--color-accent);
  }

  .spezial-badge {
    font-size: 0.5rem;
    font-weight: 700;
    padding: 0.0625rem 0.25rem;
    border-radius: 3px;
    background-color: #dbeafe;
    color: #2563eb;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  :global(.dark) .spezial-badge {
    background-color: #1e3a5f;
    color: #60a5fa;
  }

  .act.spezial-active {
    color: var(--color-accent);
    opacity: 1;
  }
</style>
