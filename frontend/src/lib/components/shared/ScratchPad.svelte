<script>
  import { onMount } from 'svelte'

  let { visible = false, onClose = () => {} } = $props()

  const STORAGE_KEY = 'bf-schnellnotiz'
  const POS_KEY = 'bf-schnellnotiz-pos'

  let text = $state('')
  let x = $state(320)
  let y = $state(80)
  let w = $state(320)
  let h = $state(260)
  let dragging = $state(false)
  let resizing = $state(false)
  let dragOff = { dx: 0, dy: 0 }
  let padEl = $state(null)

  function ladeText() {
    const saved = localStorage.getItem(STORAGE_KEY)
    text = saved || ''
  }

  onMount(() => {
    ladeText()

    const pos = localStorage.getItem(POS_KEY)
    if (pos) {
      try {
        const p = JSON.parse(pos)
        x = p.x ?? 320; y = p.y ?? 80; w = p.w ?? 320; h = p.h ?? 260
      } catch {}
    }

    // Auf externe Aenderungen reagieren (z.B. aus Buchnotizen-Toolbar)
    function onSchnellnotizUpdate() { ladeText(); }
    window.addEventListener('schnellnotiz-update', onSchnellnotizUpdate)
    return () => window.removeEventListener('schnellnotiz-update', onSchnellnotizUpdate)
  })

  function saveText() {
    localStorage.setItem(STORAGE_KEY, text)
  }

  function savePos() {
    localStorage.setItem(POS_KEY, JSON.stringify({ x, y, w, h }))
  }

  function clearPad() {
    text = ''
    localStorage.removeItem(STORAGE_KEY)
  }

  function copyAll() {
    if (text) {
      navigator.clipboard.writeText(text).catch(() => {})
    }
  }

  function startDrag(e) {
    if (e.target.closest('.sp-resize') || e.target.closest('textarea') || e.target.closest('button')) return
    dragging = true
    const rect = padEl.getBoundingClientRect()
    dragOff = { dx: e.clientX - rect.left, dy: e.clientY - rect.top }
    e.preventDefault()
  }

  function onMouseMove(e) {
    if (dragging) {
      x = Math.max(0, e.clientX - dragOff.dx)
      y = Math.max(0, e.clientY - dragOff.dy)
    }
    if (resizing) {
      w = Math.max(200, e.clientX - x)
      h = Math.max(120, e.clientY - y)
    }
  }

  function onMouseUp() {
    if (dragging || resizing) {
      dragging = false
      resizing = false
      savePos()
    }
  }

  function startResize(e) {
    resizing = true
    e.preventDefault()
    e.stopPropagation()
  }
</script>

<svelte:window onmousemove={onMouseMove} onmouseup={onMouseUp} />

{#if dragging || resizing}
  <!-- Overlay verhindert, dass iframes die Maus-Events schlucken -->
  <div class="sp-overlay" style="cursor: {resizing ? 'nwse-resize' : 'grabbing'}"></div>
{/if}

{#if visible}
  <div
    class="sp-wrap"
    bind:this={padEl}
    style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"
    role="dialog"
    aria-label="Schnellnotiz"
  >
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="sp-hd" onmousedown={startDrag}>
      <span class="sp-title"><i class="fa-solid fa-note-sticky"></i> Schnellnotiz</span>
      <div class="sp-actions">
        <button class="sp-btn" title="Alles kopieren" onclick={copyAll}>
          <i class="fa-solid fa-copy"></i>
        </button>
        <button class="sp-btn sp-btn-del" title="Inhalt loeschen" onclick={clearPad}>
          <i class="fa-solid fa-trash-can"></i>
        </button>
        <button class="sp-btn" title="Schliessen" onclick={onClose}>
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <textarea
      class="sp-text"
      bind:value={text}
      oninput={saveText}
      placeholder="Schnellnotiz hier schreiben..."
      spellcheck="false"
    ></textarea>

    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="sp-resize" onmousedown={startResize}></div>
  </div>
{/if}

<style>
  .sp-wrap {
    position: fixed;
    z-index: 9000;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    min-width: 200px;
    min-height: 120px;
  }

  .sp-hd {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid var(--glass-border);
    cursor: grab;
    user-select: none;
    flex-shrink: 0;
    background: var(--glass-bg-btn);
    border-radius: 6px 6px 0 0;
  }

  .sp-hd:active {
    cursor: grabbing;
  }

  .sp-title {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .sp-title i {
    color: var(--color-warning);
    font-size: 0.8125rem;
  }

  .sp-actions {
    display: flex;
    gap: 2px;
  }

  .sp-btn {
    background: none;
    border: none;
    color: var(--color-text-muted);
    cursor: pointer;
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 0.6875rem;
    transition: all 0.12s;
  }

  .sp-btn:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-secondary);
  }

  .sp-btn-del:hover {
    color: var(--color-error, #ef4444);
  }

  .sp-text {
    flex: 1;
    background: transparent;
    border: none;
    resize: none;
    padding: 10px 12px;
    font-size: 0.75rem;
    line-height: 1.6;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    outline: none;
  }

  .sp-text::placeholder {
    color: var(--color-text-muted);
  }

  .sp-resize {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 16px;
    height: 16px;
    cursor: nwse-resize;
  }

  .sp-resize::after {
    content: '';
    position: absolute;
    bottom: 3px;
    right: 3px;
    width: 8px;
    height: 8px;
    border-right: 2px solid var(--color-text-muted);
    border-bottom: 2px solid var(--color-text-muted);
  }

  .sp-overlay {
    position: fixed;
    inset: 0;
    z-index: 8999;
    cursor: nwse-resize;
  }
</style>
