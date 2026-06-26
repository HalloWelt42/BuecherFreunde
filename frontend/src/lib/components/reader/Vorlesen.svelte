<script>
  import { onDestroy } from "svelte";
  import { tts, sprich, stop } from "../../stores/tts.svelte.js";
  import { ladeVolltext } from "../../api/metadata.js";

  let {
    bookId,
    einheitLabel = "",
    getEinheit = null, // () => string | Promise<string>
  } = $props();

  let menuOffen = $state(false);
  let laedt = $state(false);
  let wrapperEl = $state(null);

  // Beim Verlassen des Readers laufendes Vorlesen beenden
  onDestroy(() => stop());

  async function vorlesenEinheit() {
    menuOffen = false;
    if (!getEinheit) return;
    laedt = true;
    try {
      const text = await getEinheit();
      await sprich(text, einheitLabel || "Abschnitt");
    } catch {
      /* ignore */
    } finally {
      laedt = false;
    }
  }

  async function vorlesenBuch() {
    menuOffen = false;
    laedt = true;
    try {
      const r = await ladeVolltext(bookId, 1, 100000);
      await sprich((r && r.volltext) || "", "Ganzes Buch");
    } catch {
      /* ignore */
    } finally {
      laedt = false;
    }
  }

  // Menü bei Klick ausserhalb schliessen (mit Cleanup)
  $effect(() => {
    if (!menuOffen) return;
    function aufKlick(e) {
      if (wrapperEl && !wrapperEl.contains(e.target)) menuOffen = false;
    }
    document.addEventListener("click", aufKlick, true);
    return () => document.removeEventListener("click", aufKlick, true);
  });

  // Fehlermeldung nach einigen Sekunden automatisch ausblenden
  $effect(() => {
    if (!tts.fehler) return;
    const t = setTimeout(() => {
      tts.fehler = "";
    }, 6000);
    return () => clearTimeout(t);
  });
</script>

<div class="vorlesen" bind:this={wrapperEl}>
  {#if tts.aktiv}
    <span class="tool-btn pulsiert" title="Pappagei liest vor{tts.label ? ' (' + tts.label + ')' : ''}">
      <i class="fa-solid fa-volume-high"></i>
    </span>
    <button class="tool-btn stop" onclick={stop} title="Vorlesen stoppen">
      <i class="fa-solid fa-stop"></i>
    </button>
  {:else}
    <button
      class="tool-btn"
      onclick={() => (menuOffen = !menuOffen)}
      title="Mit Pappagei vorlesen"
      disabled={laedt}
    >
      <i class="fa-solid {laedt ? 'fa-spinner fa-spin' : 'fa-volume-high'}"></i>
    </button>
    {#if menuOffen}
      <div class="vorlesen-menu">
        {#if getEinheit && einheitLabel}
          <button onclick={vorlesenEinheit}>
            <i class="fa-solid fa-volume-low"></i> {einheitLabel} vorlesen
          </button>
        {/if}
        <button onclick={vorlesenBuch}>
          <i class="fa-solid fa-book-open"></i> Ganzes Buch vorlesen
        </button>
      </div>
    {/if}
  {/if}

  {#if tts.fehler}
    <div class="vorlesen-fehler">{tts.fehler}</div>
  {/if}
</div>

<style>
  .vorlesen {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 0.125rem;
  }

  .tool-btn.stop {
    color: var(--color-error);
  }

  .pulsiert {
    color: var(--color-accent);
    animation: vorlesen-puls 1.4s ease-in-out infinite;
  }

  @keyframes vorlesen-puls {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
  }

  .vorlesen-menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    z-index: 200;
    display: flex;
    flex-direction: column;
    min-width: 190px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    padding: 0.25rem;
  }

  .vorlesen-menu button {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.625rem;
    border: none;
    background: none;
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-family: inherit;
    text-align: left;
    cursor: pointer;
    border-radius: 6px;
    white-space: nowrap;
  }

  .vorlesen-menu button:hover {
    background: var(--color-bg-tertiary);
  }

  .vorlesen-menu button i {
    color: var(--color-text-muted);
    width: 1rem;
    text-align: center;
  }

  .vorlesen-fehler {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    z-index: 200;
    width: 230px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-error);
    color: var(--color-text-primary);
    border-radius: 8px;
    padding: 0.5rem 0.625rem;
    font-size: 0.75rem;
    line-height: 1.35;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
  }
</style>
