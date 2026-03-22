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

  function toggle() {
    open = !open;
  }

  function onFarbeAendern(hlId, neueFarbe) {
    onUpdate(hlId, { color: neueFarbe });
  }
</script>

<div class="reader-hl-wrap">
  <button
    class="tool-btn"
    class:active={open}
    class:has-items={highlights.length > 0}
    onclick={toggle}
    title="Markierungen ({highlights.length})"
  >
    <i class="fa-solid fa-highlighter"></i>
    {#if highlights.length > 0}
      <span class="hl-badge">{highlights.length}</span>
    {/if}
  </button>

  {#if open}
    <div class="hl-panel">
      <div class="hl-header">
        <strong>Markierungen</strong>
        <button class="hl-close" onclick={() => { open = false; }}>
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
                <span
                  class="hl-text-preview"
                  title={hl.text_snippet}
                >
                  {hl.text_snippet?.slice(0, 60) || "Markierung"}{hl.text_snippet?.length > 60 ? "..." : ""}
                </span>
                <button
                  class="hl-goto"
                  onclick={() => onNavigate(hl)}
                  title="Zur Stelle springen"
                >
                  <i class="fa-solid fa-arrow-right"></i>
                </button>
                <button
                  class="hl-toggle"
                  onclick={() => { offen = { ...offen, [hl.id]: !offen[hl.id] }; }}
                >
                  <i class="fa-solid fa-chevron-{offen[hl.id] ? 'up' : 'down'}"></i>
                </button>
                <button class="hl-del" onclick={() => onDelete(hl.id)} title="Löschen">
                  <i class="fa-solid fa-xmark"></i>
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
    gap: 0.125rem;
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

  .hl-panel {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    width: 360px;
    max-height: 80vh;
    background: color-mix(in srgb, var(--color-bg-secondary) 85%, transparent);
    backdrop-filter: blur(20px) saturate(1.4);
    -webkit-backdrop-filter: blur(20px) saturate(1.4);
    border: 1px solid color-mix(in srgb, var(--color-border) 50%, transparent);
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 300;
  }

  .hl-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.25rem 0.5rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 30%, transparent);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    height: 28px;
  }

  .hl-header strong {
    font-weight: 600;
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
    gap: 0.25rem;
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
