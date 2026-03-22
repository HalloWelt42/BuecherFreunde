<script>
  import { materialColors } from "../../utils/colors.js";

  let {
    bookId,
    highlights = [],
    reloadTrigger = 0,
    onNavigate = () => {},
    onUpdate = () => {},
    onDelete = () => {},
  } = $props();

  let open = $state(false);
  let offen = $state({});
  let editTimer = {};

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

  function onDragMove(e) {
    if (!dragging) return;
    panelPos = {
      x: Math.max(0, Math.min(window.innerWidth - 200, e.clientX - dragOffset.x)),
      y: Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffset.y)),
    };
  }

  function onDragEnd() {
    dragging = false;
  }

  // Anzahl Labels (Highlights mit Name)
  let labelCount = $derived(highlights.filter(h => h.label_name).length);

  function toggle() {
    open = !open;
    if (!open) positioned = false;
  }

  function onFarbeAendern(hlId, neueFarbe) {
    onUpdate(hlId, { color: neueFarbe });
  }

  function onNameAendern(hlId, name) {
    clearTimeout(editTimer["name_" + hlId]);
    editTimer["name_" + hlId] = setTimeout(() => {
      onUpdate(hlId, { label_name: name });
    }, 800);
  }

  function onNotizAendern(hlId, note) {
    clearTimeout(editTimer["note_" + hlId]);
    editTimer["note_" + hlId] = setTimeout(() => {
      onUpdate(hlId, { label_note: note });
    }, 800);
  }
</script>

<svelte:window onmousemove={onDragMove} onmouseup={onDragEnd} />

{#if dragging}
  <div class="drag-overlay"></div>
{/if}

<div class="reader-hl-wrap">
  <button
    class="tool-btn"
    class:active={open}
    onclick={toggle}
    title="Markierungen ({highlights.length})"
  >
    <i class="fa-solid fa-bookmark"></i>
    {#if highlights.length > 0}
      <span class="hl-badge">{highlights.length}</span>
    {/if}
  </button>

  {#if open}
    <div
      class="hl-panel"
      class:dragging
      bind:this={panelEl}
      style={positioned ? `left: ${panelPos.x}px; top: ${panelPos.y}px; right: auto;` : ""}
    >
      <div class="hl-header" role="button" tabindex="0" onmousedown={onDragStart}>
        <i class="fa-solid fa-grip-vertical drag-handle"></i>
        <strong>Markierungen</strong>
        <span class="hl-count">{highlights.length} Stellen{#if labelCount > 0}, {labelCount} Labels{/if}</span>
        <button class="hl-close" aria-label="Markierungen schließen" onclick={() => { open = false; }}>
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      {#if highlights.length === 0}
        <div class="hl-empty">Keine Markierungen</div>
      {:else}
        <div class="hl-list">
          {#each highlights as hl (hl.id)}
            <div class="hl-entry">
              <div class="hl-row">
                <span class="hl-color-dot" style="background-color: {hl.color}"></span>
                {#if hl.label_name}
                  <span class="hl-label-name">{hl.label_name}</span>
                {:else}
                  <span class="hl-text-preview" title={hl.text_snippet}>
                    {hl.text_snippet?.slice(0, 50) || "Markierung"}{hl.text_snippet?.length > 50 ? "..." : ""}
                  </span>
                {/if}
                <button
                  class="hl-goto"
                  onclick={() => onNavigate(hl)}
                  title="Zur Stelle springen"
                >
                  <i class="fa-solid fa-arrow-right"></i>
                </button>
                <button
                  class="hl-toggle"
                  aria-label="Details ein-/ausklappen"
                  onclick={() => { offen = { ...offen, [hl.id]: !offen[hl.id] }; }}
                >
                  <i class="fa-solid fa-chevron-{offen[hl.id] ? 'up' : 'down'}"></i>
                </button>
                <button class="hl-del" onclick={() => onDelete(hl.id)} title="Markierung löschen">
                  <i class="fa-solid fa-trash-can"></i>
                </button>
              </div>

              {#if offen[hl.id]}
                <div class="hl-detail">
                  <!-- Farbauswahl -->
                  <div class="hl-colors">
                    {#each materialColors as c}
                      <button
                        class="color-dot"
                        class:active={hl.color === c.color}
                        style="background-color: {c.color}"
                        onclick={() => onFarbeAendern(hl.id, c.color)}
                        title={c.name}
                      ></button>
                    {/each}
                  </div>

                  <!-- Name (Label) -->
                  <div class="hl-field">
                    <input
                      class="hl-name-input"
                      type="text"
                      value={hl.label_name || ""}
                      oninput={(e) => onNameAendern(hl.id, e.target.value)}
                      placeholder="Label-Name (optional)"
                      maxlength="50"
                    />
                  </div>

                  <!-- Notiz -->
                  <div class="hl-field">
                    <textarea
                      class="hl-note-input"
                      value={hl.label_note || ""}
                      oninput={(e) => onNotizAendern(hl.id, e.target.value)}
                      placeholder="Notiz (optional)"
                      rows="2"
                    ></textarea>
                  </div>

                  <!-- Markierter Text (Vorschau) -->
                  {#if hl.text_snippet}
                    <div class="hl-snippet">{hl.text_snippet}</div>
                  {/if}
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
  .reader-hl-wrap {
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

  .hl-badge {
    position: absolute;
    top: -2px;
    right: -4px;
    min-width: 14px;
    height: 14px;
    padding: 0 3px;
    border-radius: 7px;
    background-color: var(--color-accent);
    color: var(--color-bg-primary);
    font-size: 0.5625rem;
    font-weight: 700;
    line-height: 14px;
    text-align: center;
  }

  .drag-overlay {
    position: fixed;
    inset: 0;
    z-index: 99998;
    cursor: grabbing;
  }

  .hl-panel {
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

  .hl-panel.dragging {
    user-select: none;
    cursor: grabbing;
  }

  .hl-header {
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

  .hl-header:active {
    cursor: grabbing;
  }

  .drag-handle {
    color: var(--color-text-muted);
    font-size: 0.5625rem;
    opacity: 0.5;
    flex-shrink: 0;
  }

  .hl-header strong {
    font-weight: 600;
  }

  .hl-count {
    flex: 1;
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    text-align: right;
    margin-right: 0.25rem;
  }

  .hl-close {
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

  .hl-close:hover {
    background: color-mix(in srgb, var(--color-bg-tertiary) 60%, transparent);
    color: var(--color-text-primary);
  }

  .hl-empty {
    padding: 0.75rem;
    text-align: center;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .hl-list {
    overflow-y: auto;
    padding: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .hl-entry {
    background: color-mix(in srgb, var(--color-bg-tertiary) 40%, transparent);
    border-radius: 5px;
    padding: 0.25rem 0.375rem;
  }

  .hl-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .hl-color-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .hl-label-name {
    flex: 1;
    min-width: 0;
    font-size: 0.6875rem;
    color: var(--color-accent);
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hl-text-preview {
    flex: 1;
    min-width: 0;
    font-size: 0.6875rem;
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hl-goto {
    flex-shrink: 0;
    border: none;
    background: none;
    color: var(--color-accent);
    font-size: 0.625rem;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
  }

  .hl-goto:hover {
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
  }

  .hl-toggle, .hl-del {
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

  .hl-toggle:hover {
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
    color: var(--color-text-primary);
  }

  .hl-del:hover {
    background: color-mix(in srgb, var(--color-error) 12%, transparent);
    color: var(--color-error);
  }

  .hl-detail {
    margin-top: 0.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .hl-colors {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }

  .color-dot {
    width: 18px;
    height: 18px;
    border: 2px solid transparent;
    border-radius: 50%;
    cursor: pointer;
    transition: transform 0.1s;
  }

  .color-dot:hover {
    transform: scale(1.2);
    border-color: var(--color-text-primary);
  }

  .color-dot.active {
    border-color: var(--color-text-primary);
    transform: scale(1.15);
  }

  .hl-field {
    display: flex;
    flex-direction: column;
  }

  .hl-name-input {
    width: 100%;
    border: 1px solid color-mix(in srgb, var(--color-border) 25%, transparent);
    border-radius: 4px;
    background: color-mix(in srgb, var(--color-bg-primary) 40%, transparent);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    padding: 0.25rem 0.375rem;
    outline: none;
    box-sizing: border-box;
  }

  .hl-name-input:focus {
    border-color: var(--color-accent);
  }

  .hl-name-input::placeholder {
    color: var(--color-text-muted);
  }

  .hl-note-input {
    width: 100%;
    border: 1px solid color-mix(in srgb, var(--color-border) 25%, transparent);
    border-radius: 4px;
    background: color-mix(in srgb, var(--color-bg-primary) 40%, transparent);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    padding: 0.25rem 0.375rem;
    outline: none;
    resize: vertical;
    line-height: 1.4;
    min-height: 2em;
    box-sizing: border-box;
  }

  .hl-note-input:focus {
    border-color: var(--color-accent);
  }

  .hl-note-input::placeholder {
    color: var(--color-text-muted);
  }

  .hl-snippet {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-style: italic;
    line-height: 1.4;
    max-height: 3.5em;
    overflow: hidden;
    padding: 0.1875rem 0.25rem;
    background: color-mix(in srgb, var(--color-bg-primary) 40%, transparent);
    border-radius: 4px;
  }
</style>
