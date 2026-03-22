<script>
  import { get, del, upload, getToken } from "../../api/client.js";
  import { ui } from "../../stores/ui.svelte.js";
  import { onMount } from "svelte";

  let bilder = $state([]);
  let laden = $state(false);
  let uploading = $state(false);

  onMount(() => {
    ladeBilder();
  });

  async function ladeBilder() {
    laden = true;
    try {
      const res = await get("/api/config/design/hintergruende");
      bilder = res.bilder || [];
      ui.bgBilder = bilder;
    } catch {
      bilder = [];
    } finally {
      laden = false;
    }
  }

  async function onDateiAuswahl(event) {
    const dateien = event.target.files;
    if (!dateien || dateien.length === 0) return;

    uploading = true;
    let erfolge = 0;
    let fehler = 0;

    for (const datei of dateien) {
      try {
        const formData = new FormData();
        formData.append("file", datei);
        await upload("/api/config/design/hintergrund", formData);
        erfolge++;
      } catch {
        fehler++;
      }
    }

    // Input zuruecksetzen
    event.target.value = "";
    uploading = false;

    if (erfolge > 0) {
      ui.toast.success(`${erfolge} Bild${erfolge > 1 ? "er" : ""} hochgeladen`);
    }
    if (fehler > 0) {
      ui.toast.error(`${fehler} Bild${fehler > 1 ? "er" : ""} fehlgeschlagen`);
    }

    await ladeBilder();
  }

  async function loescheBild(dateiname) {
    try {
      await del(`/api/config/design/hintergrund/${dateiname}`);
      ui.toast.success("Hintergrundbild entfernt");
      await ladeBilder();
    } catch {
      ui.toast.error("Bild konnte nicht entfernt werden");
    }
  }

  function bildUrl(dateiname) {
    return `/api/config/design/hintergrund/${dateiname}?token=${encodeURIComponent(getToken())}`;
  }

  let aktuellerIndex = $derived(ui.bgIndex);
  let istAktiv = $derived((dateiname) => {
    if (bilder.length === 0) return false;
    const idx = Math.min(ui.bgIndex, bilder.length - 1);
    return bilder[idx]?.dateiname === dateiname;
  });
</script>

<div class="bg-manager">
  <div class="bg-upload-row">
    <label class="upload-btn">
      <i class="fa-solid fa-cloud-arrow-up"></i>
      {uploading ? "Wird hochgeladen..." : "Bilder hochladen"}
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        onchange={onDateiAuswahl}
        disabled={uploading}
        hidden
      />
    </label>
    <span class="bg-hint">JPG, PNG oder WebP -- max. 10 MB pro Bild</span>
  </div>

  {#if laden}
    <div class="bg-loading">
      <i class="fa-solid fa-spinner fa-spin"></i> Lade Bilder...
    </div>
  {:else if bilder.length === 0}
    <div class="bg-empty">
      <i class="fa-solid fa-image"></i>
      <span>Noch keine Hintergrundbilder vorhanden</span>
    </div>
  {:else}
    <div class="bg-grid">
      {#each bilder as bild, i (bild.dateiname)}
        {@const isActive = Math.min(ui.bgIndex, bilder.length - 1) === i}
        <div class="bg-card" class:active={isActive}>
          <div class="bg-preview">
            <img src={bildUrl(bild.dateiname)} alt="Hintergrund {i + 1}" loading="lazy" />
            {#if isActive}
              <div class="bg-active-badge">
                <i class="fa-solid fa-check"></i>
              </div>
            {/if}
          </div>
          <div class="bg-card-actions">
            <button
              class="bg-select-btn"
              onclick={() => { ui.bgIndex = i; }}
              disabled={isActive}
              title="Als Hintergrund verwenden"
            >
              <i class="fa-solid fa-image"></i>
              {isActive ? "Aktiv" : "Verwenden"}
            </button>
            <button
              class="bg-delete-btn"
              onclick={() => loescheBild(bild.dateiname)}
              title="Entfernen"
            >
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
          <div class="bg-card-info">
            <span class="bg-filename">{bild.dateiname}</span>
            {#if bild.groesse}
              <span class="bg-size">{(bild.groesse / 1024 / 1024).toFixed(1)} MB</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>

    {#if bilder.length > 1}
      <div class="bg-navigation">
        <button class="nav-btn" onclick={() => ui.bgZurueck()} title="Vorheriges Bild">
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span class="nav-counter">{ui.bgIndex + 1} / {bilder.length}</span>
        <button class="nav-btn" onclick={() => ui.bgWeiter()} title="Nächstes Bild">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .bg-manager {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .bg-upload-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border: 1px dashed var(--color-accent);
    border-radius: 6px;
    background: color-mix(in srgb, var(--color-accent) 8%, transparent);
    color: var(--color-accent);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .upload-btn:hover {
    background: color-mix(in srgb, var(--color-accent) 15%, transparent);
    border-style: solid;
  }

  .bg-hint {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .bg-loading,
  .bg-empty {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1.5rem;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    justify-content: center;
  }

  .bg-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 0.75rem;
  }

  .bg-card {
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    overflow: hidden;
    background: var(--glass-bg);
    transition: border-color 0.15s;
  }

  .bg-card.active {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 1px var(--color-accent);
  }

  .bg-preview {
    position: relative;
    aspect-ratio: 16 / 10;
    overflow: hidden;
    background: var(--color-bg-tertiary);
  }

  .bg-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .bg-active-badge {
    position: absolute;
    top: 0.375rem;
    right: 0.375rem;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--color-accent);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.625rem;
  }

  .bg-card-actions {
    display: flex;
    gap: 0.375rem;
    padding: 0.5rem;
  }

  .bg-select-btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--glass-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.6875rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .bg-select-btn:hover:not(:disabled) {
    background: var(--glass-bg-btn);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .bg-select-btn:disabled {
    color: var(--color-accent);
    border-color: var(--color-accent);
    opacity: 0.7;
    cursor: default;
  }

  .bg-delete-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--glass-border);
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .bg-delete-btn:hover {
    color: var(--color-error);
    border-color: var(--color-error);
    background: color-mix(in srgb, var(--color-error) 10%, transparent);
  }

  .bg-card-info {
    display: flex;
    justify-content: space-between;
    padding: 0 0.5rem 0.375rem;
    font-size: 0.625rem;
    color: var(--color-text-muted);
  }

  .bg-filename {
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bg-navigation {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 0.5rem 0 0;
    border-top: 1px solid var(--color-border);
  }

  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.75rem;
    transition: all 0.1s;
  }

  .nav-btn:hover {
    background: var(--glass-bg-btn);
    color: var(--color-accent);
    border-color: var(--color-accent);
  }

  .nav-counter {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-text-secondary);
    min-width: 3rem;
    text-align: center;
  }
</style>
