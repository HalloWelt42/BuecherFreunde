<script>
  import { materialColors } from "../../utils/colors.js";
  import { notizenFuerBuch, erstelleNotiz, aktualisiereNotiz } from "../../api/notes.js";

  const STORAGE_KEY = "bf-schnellnotiz";

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
  let feedback = $state("");

  // Schritte: "actions" -> "colors" -> "notiz"
  let step = $state("actions");

  // Buchnotizen laden
  let buchNotizen = $state([]);
  let noteLoading = $state(false);

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
    step = "actions";
    feedback = "";
  }

  function handleMouseUp(event) {
    const target = event.target;
    if (target.closest(".epub-toolbar, .md-toolbar, .pdf-toolbar, .side-panel, .settings-float, .sel-menu, .hl-panel")) {
      return;
    }
    const sel = window.getSelection();
    const text = sel?.toString()?.trim();
    if (!text || text.length < 2) {
      visible = false;
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
    step = "actions";
    feedback = "";
  }

  function copyText() {
    navigator.clipboard.writeText(selectedText).then(() => {
      feedback = "Kopiert";
      setTimeout(() => { visible = false; feedback = ""; }, 800);
    });
  }

  function highlightWithColor(color) {
    onHighlight(selectedText, color);
    feedback = "Markiert";
    setTimeout(() => { visible = false; feedback = ""; }, 600);
  }

  // Markierten Text mit Position formatieren
  function formatSnippet() {
    return positionLabel
      ? `[${positionLabel}] "${selectedText}"`
      : `"${selectedText}"`;
  }

  // -- Schnellnotiz (localStorage) --
  function schnellnotizErsetzen() {
    localStorage.setItem(STORAGE_KEY, formatSnippet());
    window.dispatchEvent(new CustomEvent("schnellnotiz-update"));
    feedback = "Schnellnotiz ersetzt";
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  function schnellnotizAnhaengen() {
    const existing = localStorage.getItem(STORAGE_KEY) || "";
    const separator = existing ? "\n\n" : "";
    localStorage.setItem(STORAGE_KEY, existing + separator + formatSnippet());
    window.dispatchEvent(new CustomEvent("schnellnotiz-update"));
    feedback = "Angehängt";
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  // -- Buchnotiz (Backend API) --
  async function showNotizOptionen() {
    step = "notiz";
    noteLoading = true;
    try {
      buchNotizen = await notizenFuerBuch(bookId);
    } catch {
      buchNotizen = [];
    }
    noteLoading = false;
  }

  async function buchnotizNeu() {
    try {
      await erstelleNotiz(bookId, { content: formatSnippet(), page_reference: positionLabel });
      feedback = "Buchnotiz erstellt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  async function buchnotizAnhaengen(note) {
    try {
      await aktualisiereNotiz(note.id, { content: note.content + "\n\n" + formatSnippet() });
      feedback = "Angehängt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  async function buchnotizErsetzen(note) {
    try {
      await aktualisiereNotiz(note.id, { content: formatSnippet() });
      feedback = "Ersetzt";
    } catch {
      feedback = "Fehler";
    }
    setTimeout(() => { visible = false; feedback = ""; }, 800);
  }

  function close() {
    visible = false;
    step = "actions";
    feedback = "";
  }
</script>

<svelte:window onmouseup={handleMouseUp} />

{#if visible}
  <div
    class="sel-menu"
    class:expanded={step === "notiz-wahl" || step === "notiz"}
    bind:this={menuEl}
    style="left: {menuX}px; top: {menuY}px"
  >
    {#if feedback}
      <div class="sel-feedback">{feedback}</div>
    {:else if step === "actions"}
      <!-- Hauptaktionen: Markieren, Kopieren, Notiz -->
      <button class="sel-btn" onclick={() => { step = "colors"; }} title="Markieren">
        <i class="fa-solid fa-highlighter"></i>
      </button>
      <button class="sel-btn" onclick={copyText} title="Kopieren">
        <i class="fa-solid fa-copy"></i>
      </button>
      <button class="sel-btn" onclick={() => { step = "notiz-wahl"; }} title="In Notiz speichern">
        <i class="fa-solid fa-note-sticky"></i>
      </button>
    {:else if step === "colors"}
      <!-- Farbauswahl -->
      <div class="sel-colors">
        {#each materialColors as c}
          <button
            class="color-dot"
            style="background-color: {c.color}"
            onclick={() => highlightWithColor(c.color)}
            title={c.name}
          ></button>
        {/each}
      </div>
    {:else if step === "notiz-wahl"}
      <!-- Notiz-Ziel wählen -->
      <div class="sel-note-panel">
        <div class="sel-note-divider">Schnellnotiz</div>
        <button class="sel-note-btn" onclick={schnellnotizAnhaengen}>
          <i class="fa-solid fa-plus"></i> Anhängen
        </button>
        <button class="sel-note-btn warn" onclick={schnellnotizErsetzen}>
          <i class="fa-solid fa-arrow-rotate-right"></i> Ersetzen
        </button>
        <div class="sel-note-divider">Buchnotiz</div>
        <button class="sel-note-btn new" onclick={buchnotizNeu}>
          <i class="fa-solid fa-plus"></i> Neue Buchnotiz
        </button>
        <button class="sel-note-btn" onclick={showNotizOptionen}>
          <i class="fa-solid fa-list"></i> Vorhandene...
        </button>
        <button class="sel-note-btn back" onclick={() => { step = "actions"; }}>
          <i class="fa-solid fa-arrow-left"></i>
        </button>
      </div>
    {:else if step === "notiz"}
      <!-- Vorhandene Buchnotizen -->
      <div class="sel-note-panel">
        {#if noteLoading}
          <div class="sel-note-loading"><i class="fa-solid fa-spinner fa-spin"></i></div>
        {:else if buchNotizen.length === 0}
          <div class="sel-note-empty">Keine Buchnotizen vorhanden</div>
        {:else}
          <div class="sel-note-list">
            {#each buchNotizen.slice(0, 6) as note}
              <div class="sel-note-entry">
                <span class="note-preview">{note.content.slice(0, 35)}{note.content.length > 35 ? "..." : ""}</span>
                <button class="sel-note-action" onclick={() => buchnotizAnhaengen(note)} title="Anhängen">
                  <i class="fa-solid fa-plus"></i>
                </button>
                <button class="sel-note-action warn" onclick={() => buchnotizErsetzen(note)} title="Ersetzen">
                  <i class="fa-solid fa-arrow-rotate-right"></i>
                </button>
              </div>
            {/each}
          </div>
        {/if}
        <button class="sel-note-btn back" onclick={() => { step = "notiz-wahl"; }}>
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
    background: color-mix(in srgb, var(--color-bg-secondary) 90%, transparent);
    backdrop-filter: blur(12px);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  }

  .sel-menu.expanded {
    padding: 0;
    border-radius: 8px;
    backdrop-filter: blur(20px) saturate(1.4);
    background: color-mix(in srgb, var(--color-bg-secondary) 85%, transparent);
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

  .sel-colors {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    padding: 2px;
    max-width: 180px;
  }

  .color-dot {
    width: 22px;
    height: 22px;
    border: 2px solid transparent;
    border-radius: 50%;
    cursor: pointer;
    transition: transform 0.1s;
  }

  .color-dot:hover {
    transform: scale(1.2);
    border-color: var(--color-text-primary);
  }

  /* Notiz-Panel */
  .sel-note-panel {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 180px;
    max-width: 260px;
    padding: 6px;
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

  .sel-note-btn.warn {
    color: var(--color-warning, #f59e0b);
  }

  .sel-note-btn.back {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    border-top: 1px solid color-mix(in srgb, var(--color-border) 20%, transparent);
    margin-top: 2px;
    padding-top: 4px;
  }

  .sel-note-divider {
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    padding: 2px 8px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .sel-note-loading, .sel-note-empty {
    padding: 6px 8px;
    color: var(--color-text-muted);
    font-size: 0.6875rem;
  }

  .sel-note-list {
    max-height: 160px;
    overflow-y: auto;
  }

  .sel-note-entry {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 6px;
    border-radius: 4px;
  }

  .sel-note-entry:hover {
    background: color-mix(in srgb, var(--color-bg-tertiary) 60%, transparent);
  }

  .note-preview {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
  }

  .sel-note-action {
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

  .sel-note-action:hover {
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
    color: var(--color-accent);
  }

  .sel-note-action.warn:hover {
    color: var(--color-warning, #f59e0b);
  }
</style>
