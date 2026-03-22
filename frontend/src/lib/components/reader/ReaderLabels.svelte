<script>
  import { labelsFuerBuch, aktualisiereLabel, loescheLabel } from "../../api/labels.js";
  import { onMount } from "svelte";

  let {
    bookId,
    onNavigate = () => {},
  } = $props();

  let open = $state(false);
  let labels = $state([]);
  let laden = $state(false);
  let offen = $state({});
  let editTimer = {};

  // Drag-State
  let panelEl = $state(null);
  let dragging = $state(false);
  let dragOffset = { x: 0, y: 0 };
  let panelPos = $state({ x: 0, y: 0 });
  let positioned = $state(false);

  function onDragStart(e) {
    if (e.target.closest("input, textarea, button, .label-pos")) return;
    dragging = true;
    const rect = panelEl.getBoundingClientRect();
    dragOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    e.preventDefault();
  }

  function onDragMove(e) {
    if (!dragging) return;
    positioned = true;
    panelPos = {
      x: Math.max(0, Math.min(window.innerWidth - 200, e.clientX - dragOffset.x)),
      y: Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffset.y)),
    };
  }

  function onDragEnd() {
    dragging = false;
  }

  // Labels sofort laden damit Badge sichtbar ist
  onMount(() => { ladeLabels(); });

  async function ladeLabels() {
    laden = true;
    try {
      labels = await labelsFuerBuch(bookId);
    } catch { labels = []; }
    laden = false;
  }

  function toggle() {
    open = !open;
    if (open) ladeLabels();
  }

  async function onNotizAendern(labelId, neueNotiz) {
    labels = labels.map(l => l.id === labelId ? { ...l, note: neueNotiz } : l);
    clearTimeout(editTimer[labelId]);
    editTimer[labelId] = setTimeout(async () => {
      try { await aktualisiereLabel(labelId, { note: neueNotiz }); } catch {}
    }, 800);
  }

  async function onNameAendern(labelId, neuerName) {
    labels = labels.map(l => l.id === labelId ? { ...l, name: neuerName } : l);
    clearTimeout(editTimer["name_" + labelId]);
    editTimer["name_" + labelId] = setTimeout(async () => {
      try { await aktualisiereLabel(labelId, { name: neuerName }); } catch {}
    }, 800);
  }

  async function onLoeschen(labelId) {
    try {
      await loescheLabel(labelId);
      labels = labels.filter(l => l.id !== labelId);
    } catch {}
  }
</script>

<svelte:window onmousemove={onDragMove} onmouseup={onDragEnd} />

<div class="reader-labels-wrap">
  <button
    class="tool-btn"
    class:active={open}
    class:has-labels={labels.length > 0}
    onclick={toggle}
    title="Labels anzeigen ({labels.length})"
  >
    <i class="fa-solid fa-tags"></i>
    {#if labels.length > 0}
      <span class="label-badge">{labels.length}</span>
    {/if}
  </button>

  {#if open}
    <div
      class="labels-panel"
      class:dragging
      bind:this={panelEl}
      style={positioned ? `position: fixed; left: ${panelPos.x}px; top: ${panelPos.y}px; right: auto;` : ""}
    >
      <div class="labels-header" onmousedown={onDragStart}>
        <i class="fa-solid fa-grip-vertical drag-handle"></i>
        <strong>Labels</strong>
        <button class="labels-close" onclick={() => { open = false; positioned = false; }}>
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      {#if laden}
        <div class="labels-loading"><i class="fa-solid fa-spinner fa-spin"></i> Laden...</div>
      {:else if labels.length === 0}
        <div class="labels-empty">Keine Labels gesetzt</div>
      {:else}
        <div class="labels-list">
          {#each labels as label (label.id)}
            <div class="label-entry">
              <div class="label-row">
                <i class="fa-solid fa-tag" style="color: {label.color}; flex-shrink: 0;"></i>
                <input
                  class="label-name-input"
                  type="text"
                  value={label.name || ""}
                  placeholder="Name..."
                  oninput={(e) => onNameAendern(label.id, e.target.value)}
                />
                {#if label.page_reference}
                  <button
                    class="label-pos"
                    onclick={() => onNavigate(label)}
                    title="Zur Stelle springen"
                  >{label.page_reference}</button>
                {/if}
                <button
                  class="label-toggle"
                  class:has-note={!!label.note}
                  onclick={() => { offen = { ...offen, [label.id]: !offen[label.id] }; }}
                >
                  <i class="fa-solid fa-chevron-{offen[label.id] ? 'up' : 'down'}"></i>
                </button>
                <button class="label-del" onclick={() => onLoeschen(label.id)} title="Label entfernen">
                  <i class="fa-solid fa-xmark"></i>
                </button>
              </div>
              {#if offen[label.id]}
                <textarea
                  class="label-note"
                  placeholder="Notiz zum Label..."
                  value={label.note || ""}
                  oninput={(e) => onNotizAendern(label.id, e.target.value)}
                  rows={Math.max(8, Math.min(20, (label.note || "").split("\n").length + 2))}
                ></textarea>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .reader-labels-wrap {
    position: relative;
  }

  .tool-btn {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-accent);
    font-size: 1rem;
    cursor: pointer;
  }

  .tool-btn:hover, .tool-btn.active {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .label-badge {
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

  .labels-panel {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    width: 480px;
    max-height: 85vh;
    background: color-mix(in srgb, var(--color-bg-secondary) 80%, transparent);
    backdrop-filter: blur(20px) saturate(1.4);
    -webkit-backdrop-filter: blur(20px) saturate(1.4);
    border: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 300;
  }

  .labels-panel.dragging {
    user-select: none;
    cursor: grabbing;
  }

  .labels-header {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 30%, transparent);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    cursor: grab;
    height: 32px;
  }

  .labels-header:active {
    cursor: grabbing;
  }

  .labels-header strong {
    flex: 1;
    font-weight: 600;
  }

  .drag-handle {
    color: var(--color-text-muted);
    font-size: 0.625rem;
  }

  .labels-close {
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

  .labels-close:hover {
    background: color-mix(in srgb, var(--color-bg-tertiary) 60%, transparent);
    color: var(--color-text-primary);
  }

  .labels-loading, .labels-empty {
    padding: 1rem;
    text-align: center;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .labels-list {
    overflow-y: auto;
    padding: 0.375rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .label-entry {
    background: color-mix(in srgb, var(--color-bg-tertiary) 50%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border) 20%, transparent);
    border-radius: 6px;
    padding: 0.375rem 0.5rem;
  }

  .label-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .label-name-input {
    flex: 1;
    min-width: 0;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    outline: none;
    padding: 0.125rem 0.25rem;
    border-radius: 3px;
  }

  .label-name-input:focus {
    background: color-mix(in srgb, var(--color-bg-primary) 70%, transparent);
  }

  .label-name-input::placeholder {
    color: var(--color-text-muted);
  }

  .label-pos {
    flex-shrink: 0;
    border: none;
    background: none;
    color: var(--color-accent);
    font-size: 0.6875rem;
    font-family: inherit;
    cursor: pointer;
    padding: 0.0625rem 0.25rem;
    border-radius: 3px;
  }

  .label-pos:hover {
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
    text-decoration: underline;
  }

  .label-toggle {
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

  .label-toggle:hover {
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
    color: var(--color-text-primary);
  }

  .label-toggle.has-note {
    color: var(--color-accent);
  }

  .label-del {
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

  .label-del:hover {
    background: color-mix(in srgb, var(--color-error) 12%, transparent);
    color: var(--color-error);
  }

  .label-note {
    width: 100%;
    margin-top: 0.375rem;
    padding: 0.5rem;
    border: 1px solid color-mix(in srgb, var(--color-border) 30%, transparent);
    border-radius: 6px;
    background: color-mix(in srgb, var(--color-bg-primary) 60%, transparent);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: inherit;
    line-height: 1.5;
    resize: vertical;
    outline: none;
    box-sizing: border-box;
    min-height: 160px;
  }

  .label-note:focus {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-bg-primary) 80%, transparent);
  }

  .label-note::placeholder {
    color: var(--color-text-muted);
  }
</style>
