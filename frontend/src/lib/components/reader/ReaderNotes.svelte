<script>
  import { notizenFuerBuch, erstelleNotiz, aktualisiereNotiz, loescheNotiz } from "../../api/notes.js";
  import { onMount } from "svelte";

  const SCHNELLNOTIZ_KEY = "bf-schnellnotiz";

  let {
    bookId,
    positionLabel = "",
    onNavigate = () => {},
  } = $props();

  let open = $state(false);
  let notizen = $state([]);
  let laden = $state(false);
  let offen = $state({});
  let editTimer = {};
  let feedback = $state("");

  // Neue Notiz
  let neueNotiz = $state("");

  // Drag-State
  let panelEl = $state(null);
  let dragging = $state(false);
  let dragOffset = { x: 0, y: 0 };
  let panelPos = $state({ x: 0, y: 0 });
  let positioned = $state(false);

  function initPosition() {
    if (positioned || !panelEl) return;
    const rect = panelEl.getBoundingClientRect();
    panelPos = { x: rect.left, y: rect.top };
    positioned = true;
  }

  function onDragStart(e) {
    if (e.target.closest("input, textarea, button")) return;
    initPosition();
    dragging = true;
    dragOffset = { x: e.clientX - panelPos.x, y: e.clientY - panelPos.y };
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (!dragging) return;
    panelPos = {
      x: Math.max(0, Math.min(window.innerWidth - 200, e.clientX - dragOffset.x)),
      y: Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffset.y)),
    };
  }

  function onMouseUp() {
    dragging = false;
  }

  onMount(() => {
    ladeNotizen();
  });

  async function ladeNotizen() {
    laden = true;
    try {
      notizen = await notizenFuerBuch(bookId);
      // Alle Notizen standardmaessig aufklappen
      const neu = {};
      for (const n of notizen) neu[n.id] = true;
      offen = neu;
    } catch { notizen = []; }
    laden = false;
  }

  function toggle() {
    open = !open;
    if (open) {
      ladeNotizen();
    } else {
      positioned = false;
    }
  }

  async function erstellen() {
    if (!neueNotiz.trim()) return;
    try {
      const ref = positionLabel || "";
      const n = await erstelleNotiz(bookId, { content: neueNotiz, page_reference: ref });
      notizen = [n, ...notizen];
      offen = { ...offen, [n.id]: true };
      neueNotiz = "";
    } catch {}
  }

  function onInhaltAendern(noteId, neuerInhalt) {
    notizen = notizen.map(n => n.id === noteId ? { ...n, content: neuerInhalt } : n);
    clearTimeout(editTimer[noteId]);
    editTimer[noteId] = setTimeout(async () => {
      try { await aktualisiereNotiz(noteId, { content: neuerInhalt }); } catch {}
    }, 800);
  }

  async function onLoeschen(noteId) {
    try {
      await loescheNotiz(noteId);
      notizen = notizen.filter(n => n.id !== noteId);
    } catch {}
  }

  function zeigeFeedback(text) {
    feedback = text;
    setTimeout(() => { feedback = ""; }, 1200);
  }

  // Toolbar-Aktionen
  function kopieren(text) {
    navigator.clipboard.writeText(text).then(() => zeigeFeedback("Kopiert"));
  }

  function schnellnotizAnhaengen(text) {
    const existing = localStorage.getItem(SCHNELLNOTIZ_KEY) || "";
    const sep = existing ? "\n\n" : "";
    localStorage.setItem(SCHNELLNOTIZ_KEY, existing + sep + text);
    window.dispatchEvent(new CustomEvent("schnellnotiz-update"));
    zeigeFeedback("An Schnellnotiz angehängt");
  }

  function schnellnotizUeberschreiben(text) {
    localStorage.setItem(SCHNELLNOTIZ_KEY, text);
    window.dispatchEvent(new CustomEvent("schnellnotiz-update"));
    zeigeFeedback("Schnellnotiz überschrieben");
  }

  function inhaltLoeschen(noteId) {
    if (noteId === "neu") {
      neueNotiz = "";
    }
  }
</script>

<svelte:window onmousemove={onMouseMove} onmouseup={onMouseUp} />

{#if dragging}
  <div class="drag-overlay"></div>
{/if}

<div class="reader-notes-wrap">
  <button
    class="tool-btn"
    class:active={open}
    onclick={toggle}
    title="Buchnotizen ({notizen.length})"
  >
    <i class="fa-solid fa-sticky-note"></i>
    {#if notizen.length > 0}
      <span class="note-badge">{notizen.length}</span>
    {/if}
  </button>

  {#if open}
    <div
      class="notes-panel"
      class:dragging
      bind:this={panelEl}
      style="{positioned ? `position: fixed; left: ${panelPos.x}px; top: ${panelPos.y}px; right: auto;` : ''}"
    >
      <div class="notes-header" role="button" tabindex="0" onmousedown={onDragStart}>
        <i class="fa-solid fa-grip-vertical drag-handle"></i>
        <strong>Buchnotizen</strong>
        {#if feedback}
          <span class="header-feedback">{feedback}</span>
        {/if}
        <button class="notes-close" aria-label="Notizen schließen" onclick={() => { open = false; positioned = false; }}>
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Neue Notiz -->
      <div class="note-field">
        <div class="field-toolbar">
          <button class="tb" onclick={() => kopieren(neueNotiz)} disabled={!neueNotiz.trim()} title="Kopieren">
            <i class="fa-solid fa-clipboard"></i>
          </button>
          <button class="tb" onclick={() => schnellnotizAnhaengen(neueNotiz)} disabled={!neueNotiz.trim()} title="An Schnellnotiz anhängen">
            <i class="fa-solid fa-plus"></i>
          </button>
          <button class="tb" onclick={() => schnellnotizUeberschreiben(neueNotiz)} disabled={!neueNotiz.trim()} title="Schnellnotiz überschreiben">
            <i class="fa-solid fa-arrow-right-to-bracket"></i>
          </button>
          <button class="tb" onclick={() => inhaltLoeschen("neu")} disabled={!neueNotiz.trim()} title="Inhalt löschen">
            <i class="fa-solid fa-trash-can"></i>
          </button>
          <span class="tb-sep"></span>
          <button class="tb accent" onclick={erstellen} disabled={!neueNotiz.trim()} title="Als Buchnotiz speichern">
            <i class="fa-solid fa-floppy-disk"></i>
          </button>
        </div>
        <textarea
          class="field-textarea"
          bind:value={neueNotiz}
          placeholder="Neue Notiz..."
          rows="2"
          onkeydown={(e) => { if (e.key === "Enter" && e.ctrlKey) erstellen(); }}
        ></textarea>
      </div>

      {#if laden}
        <div class="notes-empty"><i class="fa-solid fa-spinner fa-spin"></i></div>
      {:else if notizen.length === 0}
        <div class="notes-empty">Keine Notizen</div>
      {:else}
        <div class="notes-list">
          {#each notizen as note (note.id)}
            <div class="note-entry">
              <div class="note-row">
                {#if note.page_reference}
                  <span class="note-ref">{note.page_reference}</span>
                {/if}
                <span class="note-preview" title={note.content}>
                  {note.content.slice(0, 50)}{note.content.length > 50 ? "..." : ""}
                </span>
                <button
                  class="note-toggle"
                  aria-label="Notiz ein-/ausklappen"
                  onclick={() => { offen = { ...offen, [note.id]: !offen[note.id] }; }}
                >
                  <i class="fa-solid fa-chevron-{offen[note.id] ? 'up' : 'down'}"></i>
                </button>
                <button class="note-del" onclick={() => onLoeschen(note.id)} title="Notiz löschen">
                  <i class="fa-solid fa-trash-can"></i>
                </button>
              </div>
              {#if offen[note.id]}
                <div class="note-field">
                  <div class="field-toolbar">
                    <button class="tb" onclick={() => kopieren(note.content)} title="Kopieren">
                      <i class="fa-solid fa-clipboard"></i>
                    </button>
                    <button class="tb" onclick={() => schnellnotizAnhaengen(note.content)} title="An Schnellnotiz anhängen">
                      <i class="fa-solid fa-plus"></i>
                    </button>
                    <button class="tb" onclick={() => schnellnotizUeberschreiben(note.content)} title="Schnellnotiz überschreiben">
                      <i class="fa-solid fa-arrow-right-to-bracket"></i>
                    </button>
                    <button class="tb danger" onclick={() => onLoeschen(note.id)} title="Notiz löschen">
                      <i class="fa-solid fa-trash-can"></i>
                    </button>
                  </div>
                  <textarea
                    class="field-textarea"
                    value={note.content}
                    oninput={(e) => onInhaltAendern(note.id, e.target.value)}
                    rows={Math.max(3, Math.min(16, note.content.split("\n").length + 1))}
                  ></textarea>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .reader-notes-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }

  .tool-btn {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .tool-btn:hover, .tool-btn.active {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .note-badge {
    position: absolute;
    top: -2px;
    right: -4px;
    min-width: 14px;
    height: 14px;
    padding: 0 3px;
    border-radius: 7px;
    background-color: var(--color-warning, #f59e0b);
    color: #000;
    font-size: 0.5625rem;
    font-weight: 700;
    line-height: 14px;
    text-align: center;
  }

  .notes-panel {
    position: fixed;
    top: 50px;
    right: 10px;
    width: 50%;
    max-width: 600px;
    min-width: 300px;
    max-height: 80vh;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    display: flex;
    flex-direction: column;
    z-index: 99999;
  }

  .notes-panel.dragging {
    user-select: none;
    cursor: grabbing;
  }

  .notes-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid var(--glass-border);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    height: 28px;
    cursor: grab;
  }

  .notes-header:active {
    cursor: grabbing;
  }

  .notes-header strong {
    flex: 1;
    font-weight: 600;
  }

  .header-feedback {
    font-size: 0.625rem;
    color: var(--color-accent);
    font-weight: 600;
    white-space: nowrap;
  }

  .drag-handle {
    color: var(--color-text-muted);
    font-size: 0.625rem;
  }

  .notes-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 3px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.625rem;
  }

  .notes-close:hover {
    background: var(--glass-bg-btn);
    color: var(--color-text-primary);
  }

  /* Notiz-Feld mit Toolbar */
  .note-field {
    display: flex;
    flex-direction: column;
    margin: 0.25rem 0.375rem;
    border-radius: 6px;
    background: var(--glass-bg-btn-alt);
    border: 1px solid var(--glass-border);
    overflow: hidden;
  }

  .field-toolbar {
    display: flex;
    align-items: center;
    gap: 1px;
    padding: 2px 3px;
    border-bottom: 1px solid var(--glass-border);
    background: var(--glass-bg-btn);
  }

  .tb-sep {
    width: 1px;
    height: 14px;
    background: var(--glass-border);
    margin: 0 2px;
  }

  .tb {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 3px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.5625rem;
    flex-shrink: 0;
  }

  .tb:hover:not(:disabled) {
    background: var(--glass-bg-btn);
    color: var(--color-text-primary);
  }

  .tb:disabled {
    opacity: 0.2;
    cursor: default;
  }

  .tb.accent {
    color: var(--color-accent);
  }

  .tb.accent:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-accent) 15%, transparent);
    color: var(--color-accent);
  }

  .tb.danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-error) 12%, transparent);
    color: var(--color-error);
  }

  .field-textarea {
    width: 100%;
    border: none;
    background: transparent;
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: inherit;
    padding: 0.375rem;
    resize: vertical;
    outline: none;
    line-height: 1.5;
    min-height: 2.5em;
    box-sizing: border-box;
  }

  .field-textarea::placeholder {
    color: var(--color-text-muted);
  }

  .notes-empty {
    padding: 0.75rem;
    text-align: center;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .notes-list {
    overflow-y: auto;
    padding: 0.25rem 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .note-entry {
    padding: 0 0.125rem;
  }

  .note-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.125rem 0.375rem;
  }

  .note-ref {
    font-size: 0.5625rem;
    color: var(--color-accent);
    flex-shrink: 0;
    font-weight: 600;
  }

  .note-preview {
    flex: 1;
    min-width: 0;
    font-size: 0.6875rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .note-toggle, .note-del {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: 3px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.5rem;
    cursor: pointer;
    flex-shrink: 0;
  }

  .note-toggle:hover {
    background: var(--glass-bg-btn);
    color: var(--color-text-primary);
  }

  .note-del:hover {
    background: color-mix(in srgb, var(--color-error) 12%, transparent);
    color: var(--color-error);
  }

  .drag-overlay {
    position: fixed;
    inset: 0;
    z-index: 99998;
    cursor: grabbing;
  }
</style>
