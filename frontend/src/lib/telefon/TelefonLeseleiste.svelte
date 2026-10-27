<script>
  // Rahmen der Leser am Telefon: oben Zurück, Titel und Stand, unten die Werkzeuge des Formats, dazwischen die
  // Lesefläche. Die Vollansicht blendet beide Leisten aus (und nimmt, wo das Gerät es erlaubt, den ganzen Bildschirm);
  // ein kleiner Knopf oben rechts holt sie zurück.
  let { titel = "", stand = "", onBack = () => {}, werkzeuge, children } = $props();

  let vollansicht = $state(false);

  function vollbildAktiv() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement);
  }

  async function vollansichtAn() {
    vollansicht = true;
    const el = document.documentElement;
    try {
      if (el.requestFullscreen) await el.requestFullscreen();
      else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
    } catch { /* Gerät erlaubt kein Vollbild: die Leisten sind trotzdem weg */ }
  }

  async function vollansichtAus() {
    vollansicht = false;
    if (!vollbildAktiv()) return;
    try {
      if (document.exitFullscreen) await document.exitFullscreen();
      else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
    } catch { /* bereits verlassen */ }
  }

  // Verlässt man das Vollbild mit einer Geste des Geräts, kommen die Leisten zurück
  $effect(() => {
    function beiWechsel() {
      if (!vollbildAktiv()) vollansicht = false;
    }
    document.addEventListener("fullscreenchange", beiWechsel);
    document.addEventListener("webkitfullscreenchange", beiWechsel);
    return () => {
      document.removeEventListener("fullscreenchange", beiWechsel);
      document.removeEventListener("webkitfullscreenchange", beiWechsel);
      if (vollbildAktiv()) vollansichtAus();
    };
  });
</script>

<div class="leser-telefon">
  {#if !vollansicht}
    <header class="oben">
      <button class="knopf" onclick={onBack} aria-label="Zurück">
        <i class="fa-solid fa-arrow-left"></i>
      </button>
      <div class="kopf">
        <span class="titel">{titel}</span>
        {#if stand}<span class="stand">{stand}</span>{/if}
      </div>
      <button class="knopf" onclick={vollansichtAn} aria-label="Vollansicht">
        <i class="fa-solid fa-expand"></i>
      </button>
    </header>
  {/if}

  <div class="flaeche">
    {@render children()}
  </div>

  {#if !vollansicht && werkzeuge}
    <nav class="unten">
      {@render werkzeuge()}
    </nav>
  {/if}

  {#if vollansicht}
    <button class="leisten-zeigen" onclick={vollansichtAus} aria-label="Leisten zeigen">
      <i class="fa-solid fa-compress"></i>
    </button>
  {/if}
</div>

<style>
  .leser-telefon {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .oben {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: env(safe-area-inset-top) 0.25rem 0;
    min-height: calc(52px + env(safe-area-inset-top));
    background: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
  }

  .kopf {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }

  .titel {
    font-size: 16px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .stand {
    font-size: 14px;
    color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .flaeche {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .unten {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-around;
    gap: 0.25rem;
    min-height: 52px;
    padding: 0 0.25rem;
    background: var(--color-bg-secondary);
    border-top: 1px solid var(--color-border);
  }

  .knopf,
  .unten :global(button) {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    min-width: 44px;
    height: 44px;
    border: none;
    border-radius: 10px;
    background: none;
    color: var(--color-text-primary);
    font: inherit;
    font-size: 1.0625rem;
  }

  .unten :global(button.umschalter) {
    padding: 0 0.75rem;
    font-size: 15px;
    font-weight: 600;
    border: 1px solid var(--color-border);
  }

  .unten :global(button:disabled) {
    opacity: 0.35;
  }

  .unten :global(button.aktiv) {
    color: var(--color-accent);
    background: var(--color-accent-light);
  }

  .leisten-zeigen {
    position: absolute;
    top: calc(0.5rem + env(safe-area-inset-top));
    right: 0.5rem;
    z-index: 50;
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    opacity: 0.55;
  }
</style>
