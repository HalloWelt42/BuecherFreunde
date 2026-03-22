<script>
  import { get, patch } from "../../api/client.js";
  import { onMount } from "svelte";

  let config = $state({ url: "", modell: "", aktiviert: false });
  let status = $state(null);
  let prompts = $state([]);
  let laden = $state(true);
  let editingPrompt = $state(null);
  let saving = $state(false);
  let statusMsg = $state("");
  let modelSaving = $state(false);
  let urlEdit = $state("");
  let urlSaving = $state(false);
  let scanLaden = $state(false);
  let scanErgebnisse = $state([]);

  async function urlSpeichern() {
    if (!urlEdit.trim() || urlSaving) return;
    urlSaving = true;
    try {
      config = await patch("/api/ai/config", { lm_studio_url: urlEdit.trim() });
      statusMsg = "URL gespeichert";
      await verbindungTesten();
    } catch (e) {
      statusMsg = "Fehler: " + e.message;
    } finally {
      urlSaving = false;
      setTimeout(() => (statusMsg = ""), 3000);
    }
  }

  async function netzwerkScannen() {
    scanLaden = true;
    scanErgebnisse = [];
    statusMsg = "Scanne lokales Netzwerk...";
    try {
      const result = await get("/api/ai/scan");
      scanErgebnisse = result.gefunden || [];
      statusMsg = scanErgebnisse.length > 0
        ? `${scanErgebnisse.length} LM Studio Instanz(en) gefunden`
        : "Keine LM Studio Instanz gefunden";
    } catch (e) {
      statusMsg = "Scan fehlgeschlagen: " + e.message;
    } finally {
      scanLaden = false;
      setTimeout(() => (statusMsg = ""), 5000);
    }
  }

  function scanErgebnisUebernehmen(url) {
    urlEdit = url;
    scanErgebnisse = [];
  }

  async function ladeAlles() {
    laden = true;
    try {
      const [cfg, st, pr] = await Promise.all([
        get("/api/ai/config"),
        get("/api/ai/status").catch(() => null),
        get("/api/ai/prompts").catch(() => []),
      ]);
      config = cfg;
      status = st;
      prompts = pr;
      urlEdit = cfg.url || "";
    } catch (e) {
      console.error("AI-Einstellungen laden fehlgeschlagen:", e);
    } finally {
      laden = false;
    }
  }

  function startEdit(prompt) {
    editingPrompt = {
      id: prompt.id,
      name: prompt.name,
      beschreibung: prompt.beschreibung,
      system_prompt: prompt.system_prompt,
      temperatur: prompt.temperatur,
      max_tokens: prompt.max_tokens,
      aktiv: !!prompt.aktiv,
    };
  }

  function cancelEdit() {
    editingPrompt = null;
  }

  async function savePrompt() {
    if (!editingPrompt) return;
    saving = true;
    try {
      await patch(`/api/ai/prompts/${editingPrompt.id}`, {
        name: editingPrompt.name,
        beschreibung: editingPrompt.beschreibung,
        system_prompt: editingPrompt.system_prompt,
        temperatur: editingPrompt.temperatur,
        max_tokens: editingPrompt.max_tokens,
        aktiv: editingPrompt.aktiv,
      });
      statusMsg = "Prompt gespeichert";
      editingPrompt = null;
      await ladeAlles();
      setTimeout(() => (statusMsg = ""), 2000);
    } catch (e) {
      statusMsg = "Fehler: " + e.message;
    } finally {
      saving = false;
    }
  }

  async function verbindungTesten() {
    statusMsg = "Teste Verbindung...";
    try {
      status = await get("/api/ai/status");
      statusMsg = status?.erreichbar ? "Verbindung erfolgreich" : "Nicht erreichbar";
    } catch {
      statusMsg = "Verbindungstest fehlgeschlagen";
    }
    setTimeout(() => (statusMsg = ""), 3000);
  }

  let verfuegbareModelle = $derived(status?.modelle || []);

  async function modellWechseln(e) {
    const neuesModell = e.target.value;
    modelSaving = true;
    try {
      config = await patch("/api/ai/config", { lm_studio_model: neuesModell });
      statusMsg = "Modell gewechselt: " + neuesModell;
      setTimeout(() => (statusMsg = ""), 2000);
    } catch (err) {
      statusMsg = "Fehler: " + err.message;
    } finally {
      modelSaving = false;
    }
  }

  function maskToken(url) {
    // URL anzeigen, aber ggf. Token/Passwort maskieren
    try {
      const u = new URL(url);
      if (u.password) {
        u.password = "****";
      }
      return u.toString();
    } catch {
      return url;
    }
  }

  onMount(ladeAlles);
</script>

<div class="ai-settings">
  {#if laden}
    <div class="loading">
      <i class="fa-solid fa-spinner fa-spin"></i> Laden...
    </div>
  {:else}
    <!-- Verbindung -->
    <section class="section">
      <h2 class="section-title">
        <i class="fa-solid fa-plug"></i> LM Studio Verbindung
      </h2>
      <div class="conn-grid">
        <div class="conn-row">
          <span class="conn-label">Status</span>
          <span class="conn-value">
            <span
              class="status-dot"
              class:online={status?.erreichbar}
              class:offline={!status?.erreichbar}
            ></span>
            {status?.erreichbar ? "Verbunden" : "Nicht erreichbar"}
          </span>
        </div>
        <div class="conn-row">
          <span class="conn-label">URL</span>
          <div class="url-edit-row">
            <input
              type="text"
              class="url-input"
              bind:value={urlEdit}
              placeholder="http://192.168.1.100:1234"
              onkeydown={(e) => { if (e.key === "Enter") urlSpeichern(); }}
            />
            <button class="btn-test" onclick={urlSpeichern} disabled={urlSaving} title="URL speichern und testen">
              {#if urlSaving}
                <i class="fa-solid fa-spinner fa-spin"></i>
              {:else}
                <i class="fa-solid fa-check"></i>
              {/if}
            </button>
          </div>
        </div>
        <div class="conn-row">
          <span class="conn-label">Modell</span>
          {#if verfuegbareModelle.length > 0}
            <select class="model-select" value={config.modell} onchange={modellWechseln} disabled={modelSaving}>
              {#each verfuegbareModelle as m}
                <option value={m} selected={m === config.modell}>{m}</option>
              {/each}
            </select>
            {#if modelSaving}<i class="fa-solid fa-spinner fa-spin spin-small"></i>{/if}
          {:else}
            <code class="conn-url">{config.modell}</code>
          {/if}
        </div>
        <div class="conn-row">
          <span class="conn-label">Aktiviert</span>
          <span class="conn-value" class:active={config.aktiviert}>
            {config.aktiviert ? "Ja" : "Nein"}
          </span>
        </div>
      </div>
      <div class="conn-actions">
        <button class="btn-test" onclick={verbindungTesten} title="Verbindung zur eingestellten URL testen">
          <i class="fa-solid fa-rotate"></i> Testen
        </button>
        <button class="btn-test" onclick={netzwerkScannen} disabled={scanLaden} title="Lokales Netzwerk nach LM Studio durchsuchen">
          {#if scanLaden}
            <i class="fa-solid fa-spinner fa-spin"></i>
          {:else}
            <i class="fa-solid fa-magnifying-glass"></i>
          {/if}
          Netzwerk scannen
        </button>
        {#if statusMsg}
          <span class="status-msg">{statusMsg}</span>
        {/if}
      </div>

      {#if scanErgebnisse.length > 0}
        <div class="scan-results">
          <span class="scan-label">Gefunden:</span>
          {#each scanErgebnisse as treffer}
            <button class="scan-hit" onclick={() => scanErgebnisUebernehmen(treffer.url)} title="Diese URL übernehmen">
              <i class="fa-solid fa-server"></i>
              {treffer.url}
              {#if treffer.modelle}
                <span class="scan-models">({treffer.modelle} Modelle)</span>
              {/if}
            </button>
          {/each}
        </div>
      {/if}

      <p class="hint">
        LM Studio ist eine kostenlose Software für lokale KI-Modelle. Starte LM Studio auf einem Rechner in deinem Netzwerk, lade ein Modell und trage die URL hier ein. "Netzwerk scannen" findet LM Studio automatisch.
      </p>
    </section>

    <!-- Prompts -->
    <section class="section">
      <h2 class="section-title">
        <i class="fa-solid fa-message"></i> Prompts
        {#if prompts.length}<span class="badge">{prompts.length}</span>{/if}
      </h2>

      {#if editingPrompt}
        <div class="prompt-edit">
          <div class="edit-header">
            <input
              type="text"
              class="edit-name"
              bind:value={editingPrompt.name}
              placeholder="Prompt-Name"
            />
            <label class="edit-toggle">
              <input type="checkbox" bind:checked={editingPrompt.aktiv} />
              Aktiv
            </label>
          </div>
          <input
            type="text"
            class="edit-desc"
            bind:value={editingPrompt.beschreibung}
            placeholder="Beschreibung..."
          />
          <label class="edit-label" for="edit-system-prompt">System-Prompt</label>
          <textarea
            id="edit-system-prompt"
            class="edit-textarea"
            bind:value={editingPrompt.system_prompt}
            rows="10"
          ></textarea>
          <div class="edit-params">
            <div class="param">
              <label for="edit-temperatur">Temperatur</label>
              <input
                id="edit-temperatur"
                type="number"
                class="param-input"
                bind:value={editingPrompt.temperatur}
                min="0"
                max="2"
                step="0.1"
              />
            </div>
            <div class="param">
              <label for="edit-max-tokens">Max Tokens</label>
              <input
                id="edit-max-tokens"
                type="number"
                class="param-input"
                bind:value={editingPrompt.max_tokens}
                min="50"
                max="4000"
                step="50"
              />
            </div>
          </div>
          <div class="edit-actions">
            <button class="btn-save" onclick={savePrompt} disabled={saving}>
              {#if saving}<i class="fa-solid fa-spinner fa-spin"></i>{:else}<i class="fa-solid fa-check"></i>{/if}
              Speichern
            </button>
            <button class="btn-cancel" onclick={cancelEdit}>Abbrechen</button>
          </div>
        </div>
      {/if}

      <div class="prompt-list">
        {#each prompts as prompt (prompt.id)}
          <div class="prompt-card" class:inactive={!prompt.aktiv} class:editing={editingPrompt?.id === prompt.id}>
            <div class="prompt-head">
              <span class="prompt-key">{prompt.schluessel}</span>
              <span class="prompt-name">{prompt.name}</span>
              {#if !prompt.aktiv}
                <span class="inactive-badge">Inaktiv</span>
              {/if}
              <button class="btn-edit" onclick={() => startEdit(prompt)} title="Bearbeiten">
                <i class="fa-solid fa-pen"></i>
              </button>
            </div>
            {#if prompt.beschreibung}
              <p class="prompt-desc">{prompt.beschreibung}</p>
            {/if}
            <div class="prompt-meta">
              <span class="meta-item" title="Temperatur">
                <i class="fa-solid fa-temperature-half"></i> {prompt.temperatur}
              </span>
              <span class="meta-item" title="Max Tokens">
                <i class="fa-solid fa-coins"></i> {prompt.max_tokens}
              </span>
            </div>
            <pre class="prompt-preview">{prompt.system_prompt}</pre>
          </div>
        {/each}
        {#if prompts.length === 0}
          <div class="empty">Keine Prompts konfiguriert.</div>
        {/if}
      </div>
    </section>
  {/if}
</div>

<style>
  .ai-settings {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .loading {
    padding: 2rem;
    text-align: center;
    color: var(--color-text-muted);
    font-size: 0.8125rem;
  }

  .section {
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-secondary);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .section-title i {
    color: var(--color-accent);
    font-size: 0.8125rem;
  }

  .badge {
    font-size: 0.625rem;
    font-weight: 600;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.3125rem;
    border-radius: 999px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  /* Verbindung */
  .conn-grid {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .conn-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .conn-label {
    font-size: 0.6875rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    min-width: 70px;
  }

  .conn-value {
    font-size: 0.8125rem;
    color: var(--color-text-primary);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .conn-value.active {
    color: var(--color-success);
  }

  .conn-url {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background: var(--glass-placeholder);
    padding: 0.1875rem 0.375rem;
    border-radius: 4px;
    border: 1px solid var(--glass-border);
  }

  .url-edit-row {
    display: flex;
    gap: 0.375rem;
    align-items: center;
    flex: 1;
  }

  .url-input {
    flex: 1;
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--color-text-primary);
    background: var(--glass-placeholder);
    backdrop-filter: blur(var(--glass-blur-btn));
    padding: 0.375rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--glass-border);
  }

  .url-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .scan-results {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.5rem;
  }

  .scan-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .scan-hit {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.625rem;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, #22c55e 40%, transparent);
    background: color-mix(in srgb, #22c55e 10%, transparent);
    color: #22c55e;
    font-size: 0.75rem;
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all 0.15s;
  }

  .scan-hit:hover {
    background: color-mix(in srgb, #22c55e 20%, transparent);
  }

  .scan-models {
    font-family: var(--font-sans);
    opacity: 0.7;
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-dot.online { background-color: var(--color-success); }
  .status-dot.offline { background-color: var(--color-error); }

  .model-select {
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    cursor: pointer;
    max-width: 400px;
  }

  .model-select:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .model-select:disabled {
    opacity: 0.5;
  }

  .spin-small {
    font-size: 0.6875rem;
    color: var(--color-accent);
    margin-left: 0.25rem;
  }

  .conn-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .btn-test {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: none;
    color: var(--color-text-secondary);
    font-size: 0.6875rem;
    cursor: pointer;
    transition: all 0.1s;
  }

  .btn-test:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  .status-msg {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .hint {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin: 0;
  }


  /* Prompt-Editor */
  .prompt-edit {
    padding: 0.75rem;
    border: 1px solid var(--color-accent);
    border-radius: 8px;
    background-color: var(--color-bg-primary);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .edit-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .edit-name {
    flex: 1;
    padding: 0.3125rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    font-weight: 600;
    font-family: var(--font-sans);
  }

  .edit-name:focus { outline: none; border-color: var(--color-accent); }

  .edit-toggle {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.6875rem;
    color: var(--color-text-secondary);
    cursor: pointer;
    white-space: nowrap;
  }

  .edit-toggle input {
    accent-color: var(--color-accent);
  }

  .edit-desc {
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-secondary);
    font-size: 0.75rem;
    font-family: var(--font-sans);
  }

  .edit-desc:focus { outline: none; border-color: var(--color-accent); }

  .edit-label {
    font-size: 0.625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .edit-textarea {
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    line-height: 1.5;
    resize: vertical;
    min-height: 120px;
  }

  .edit-textarea:focus { outline: none; border-color: var(--color-accent); }

  .edit-params {
    display: flex;
    gap: 1rem;
  }

  .param {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .param label {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .param-input {
    width: 70px;
    padding: 0.25rem 0.375rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background-color: var(--color-bg-secondary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: var(--font-mono);
    text-align: center;
  }

  .param-input:focus { outline: none; border-color: var(--color-accent); }

  .edit-actions {
    display: flex;
    gap: 0.25rem;
  }

  .btn-save {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.625rem;
    border: none;
    border-radius: 5px;
    background-color: var(--color-accent);
    color: #fff;
    font-size: 0.6875rem;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-save:disabled { opacity: 0.5; cursor: default; }

  .btn-cancel {
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.6875rem;
    cursor: pointer;
  }

  .btn-cancel:hover {
    background-color: var(--color-bg-tertiary);
  }

  /* Prompt-Liste */
  .prompt-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .prompt-card {
    padding: 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background-color: var(--color-bg-primary);
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    transition: border-color 0.1s;
  }

  .prompt-card:hover {
    border-color: var(--color-text-muted);
  }

  .prompt-card.inactive {
    opacity: 0.5;
  }

  .prompt-card.editing {
    border-color: var(--color-accent);
  }

  .prompt-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .prompt-key {
    font-size: 0.5625rem;
    font-weight: 700;
    font-family: var(--font-mono);
    padding: 0.0625rem 0.3125rem;
    border-radius: 3px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .prompt-name {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    flex: 1;
  }

  .inactive-badge {
    font-size: 0.5rem;
    font-weight: 600;
    padding: 0.0625rem 0.25rem;
    border-radius: 3px;
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-muted);
  }

  .btn-edit {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.375rem;
    height: 1.375rem;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.5625rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.1s;
  }

  .prompt-card:hover .btn-edit { opacity: 1; }

  .btn-edit:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-accent);
  }

  .prompt-desc {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin: 0;
  }

  .prompt-meta {
    display: flex;
    gap: 0.75rem;
  }

  .meta-item {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .meta-item i {
    font-size: 0.5625rem;
  }

  .prompt-preview {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-secondary);
    padding: 0.5rem;
    border-radius: 5px;
    border: 1px solid var(--color-border);
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.4;
    max-height: 120px;
    overflow-y: auto;
    margin: 0;
  }

  .empty {
    padding: 1.5rem;
    text-align: center;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
