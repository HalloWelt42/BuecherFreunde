<script>
  import { erstelleNotiz, notizenFuerBuch, aktualisiereNotiz } from "../../api/notes.js";

  let {
    bookId,
    positionLabel = "",
    externalSelection = null,
    onHighlight = () => {},
  } = $props();

  let menuEl = $state(null);
  let visible = $state(false);
  let menuX = $state(0);
  let menuY = $state(0);
  let selectedText = $state("");
  let showNoteChoice = $state(false);
  let existingNotes = $state([]);
  let noteLoading = $state(false);
  let feedback = $state("");

  // Externe Selection (z.B. aus EPUB-iframe)
  $effect(() => {
    if (externalSelection?.text) {
      showFromExternal(externalSelection);
    }
  });

  function showFromExternal(sel) {
    selectedText = sel.text;
    const menuH = 44;
    let y = sel.y - 8;
    if (y < menuH + 8) y = sel.y + 30 + menuH;
    let x = Math.max(80, Math.min(window.innerWidth - 80, sel.x));
    menuX = x;
    menuY = y;
    visible = true;
    showNoteChoice = false;
    feedback = "";
  }

  function handleMouseUp(event) {
    // Nur im Lesebereich reagieren, nicht in Toolbar/Panels
    const target = event.target;
    if (target.closest(".epub-toolbar, .md-toolbar, .pdf-toolbar, .side-panel, .settings-float, .sel-menu, .label-picker")) {
      return;
    }
    const sel = window.getSelection();
    const text = sel?.toString()?.trim();
    if (!text || text.length < 2) {
      visible = false;
      showNoteChoice = false;
      return;
    }
    selectedText = text;
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const menuH = 44;
    let y = rect.top - 8;
    if (y < menuH + 8) y = rect.bottom + 8 + menuH;
    let x = rect.left + rect.width / 2;
    x = Math.max(80, Math.min(window.innerWidth - 80, x));
    menuX = x;
    menuY = y;
    visible = true;
    showNoteChoice = false;
    feedback = "";
  }

  function copyText() {
    navigator.clipboard.writeText(selectedText).then(() => {
      feedback = "Kopiert";
      setTimeout(() => { visible = false; feedback = ""; }, 800);
    });
  }

  function highlightText() {
    onHighlight(selectedText, positionLabel);
    feedback = "Markiert";
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  async function showNoteOptions() {
    showNoteChoice = true;
    noteLoading = true;
    try {
      existingNotes = await notizenFuerBuch(bookId);
    } catch {
      existingNotes = [];
    }
    noteLoading = false;
  }

  async function createNewNote() {
    const content = positionLabel
      ? `[${positionLabel}] "${selectedText}"`
      : `"${selectedText}"`;
    try {
      await erstelleNotiz(bookId, { content, page_reference: positionLabel });
      feedback = "Notiz erstellt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; showNoteChoice = false; feedback = ""; }, 1000);
  }

  async function appendToNote(note) {
    const append = positionLabel
      ? `\n\n[${positionLabel}] "${selectedText}"`
      : `\n\n"${selectedText}"`;
    try {
      await aktualisiereNotiz(note.id, { content: note.content + append });
      feedback = "Angehängt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; showNoteChoice = false; feedback = ""; }, 1000);
  }

  async function replaceNote(note) {
    const content = positionLabel
      ? `[${positionLabel}] "${selectedText}"`
      : `"${selectedText}"`;
    try {
      await aktualisiereNotiz(note.id, { content });
      feedback = "Ersetzt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; showNoteChoice = false; feedback = ""; }, 1000);
  }
</script>

<svelte:window onmouseup={handleMouseUp} />

{#if visible}
  <div
    class="sel-menu"
    bind:this={menuEl}
    style="left: {menuX}px; top: {menuY}px"
  >
    {#if feedback}
      <div class="sel-feedback">{feedback}</div>
    {:else if !showNoteChoice}
      <button class="sel-btn" onclick={highlightText} title="Text wie mit Edding markieren">
        <i class="fa-solid fa-highlighter"></i>
      </button>
      <button class="sel-btn" onclick={copyText} title="Text in die Zwischenablage kopieren">
        <i class="fa-solid fa-copy"></i>
      </button>
      <button class="sel-btn" onclick={showNoteOptions} title="Als Notiz speichern oder an bestehende Notiz anhängen">
        <i class="fa-solid fa-note-sticky"></i>
      </button>
    {:else}
      <div class="sel-note-panel">
        <button class="sel-note-btn new" onclick={createNewNote} title="Neue Notiz mit dieser Textstelle erstellen">
          <i class="fa-solid fa-plus"></i> Neue Notiz
        </button>
        {#if noteLoading}
          <div class="sel-note-loading"><i class="fa-solid fa-spinner fa-spin"></i></div>
        {:else if existingNotes.length > 0}
          <div class="sel-note-divider">Anhängen an:</div>
          <div class="sel-note-list">
            {#each existingNotes.slice(0, 5) as note}
              <div class="sel-note-item">
                <button class="sel-note-btn append" onclick={() => appendToNote(note)} title="Textstelle an diese Notiz anhängen">
                  <i class="fa-solid fa-plus"></i>
                  <span class="note-preview">{note.content.slice(0, 40)}{note.content.length > 40 ? "..." : ""}</span>
                </button>
                <button class="sel-note-replace" onclick={() => replaceNote(note)} title="Diese Notiz mit der Textstelle ersetzen">
                  <i class="fa-solid fa-rotate"></i>
                </button>
              </div>
            {/each}
          </div>
        {/if}
        <button class="sel-note-btn back" onclick={() => { showNoteChoice = false; }} title="Zurück">
          <i class="fa-solid fa-arrow-left"></i>
        </button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .sel-menu {
    position: fixed;
    transform: translate(-50%, -100%);
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 4px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  }

  .sel-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.875rem;
  }

  .sel-btn:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-accent);
  }

  .sel-feedback {
    padding: 4px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-accent);
    white-space: nowrap;
  }

  .sel-note-panel {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 180px;
    max-width: 260px;
  }

  .sel-note-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 8px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.75rem;
    text-align: left;
  }

  .sel-note-btn:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .sel-note-btn.new {
    color: var(--color-accent);
    font-weight: 600;
  }

  .sel-note-btn.back {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .sel-note-divider {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    padding: 2px 8px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .sel-note-list {
    max-height: 120px;
    overflow-y: auto;
  }

  .sel-note-item {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .sel-note-item .sel-note-btn.append {
    flex: 1;
    min-width: 0;
  }

  .note-preview {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sel-note-replace {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: 0.625rem;
    flex-shrink: 0;
  }

  .sel-note-replace:hover {
    background: var(--color-bg-tertiary);
    color: var(--color-error);
  }

  .sel-note-loading {
    padding: 4px 8px;
    color: var(--color-text-muted);
    font-size: 0.75rem;
  }
</style>
