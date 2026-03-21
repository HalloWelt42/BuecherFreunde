<script>
  import { kiStatus, healthCheck, ladeConfig } from "../../api/config.js";
  import { onMount } from "svelte";

  let services = $state([]);
  let laden = $state(true);

  onMount(() => {
    pruefeServices();
  });

  async function pruefeServices() {
    laden = true;
    const ergebnisse = [];
    let config = null;

    // Backend
    try {
      const health = await healthCheck();
      ergebnisse.push({
        name: "Backend API",
        icon: "fa-server",
        status: "online",
        info: `v${health.version}`,
        url: window.location.origin + "/api",
      });
    } catch {
      ergebnisse.push({
        name: "Backend API",
        icon: "fa-server",
        status: "offline",
        info: "Nicht erreichbar",
        url: null,
      });
    }

    // Konfiguration laden
    try {
      config = await ladeConfig();
    } catch { /* still */ }

    if (config) {
      // Frontend
      ergebnisse.push({
        name: "Frontend",
        icon: "fa-display",
        status: "online",
        info: `Port ${config.external_port}`,
        url: `http://localhost:${config.external_port}`,
      });

      // Google Books
      ergebnisse.push({
        name: "Google Books",
        icon: "fa-g",
        status: config.google_books?.aktiviert ? "online" : "deaktiviert",
        info: config.google_books?.aktiviert
          ? config.google_books.hat_api_key ? "Mit API-Key" : "Ohne API-Key (eingeschränkt)"
          : "Deaktiviert",
        url: config.google_books?.aktiviert ? "https://www.googleapis.com/books/v1" : null,
      });

      // Open Library
      ergebnisse.push({
        name: "Open Library",
        icon: "fa-book-open",
        status: config.openlibrary?.aktiviert ? "online" : "deaktiviert",
        info: config.openlibrary?.aktiviert
          ? `Rate-Limit: ${config.openlibrary.rate_limit}/s`
          : "Deaktiviert",
        url: config.openlibrary?.aktiviert ? "https://openlibrary.org/api" : null,
      });

      // LM Studio
      if (config.lm_studio?.aktiviert) {
        try {
          const ki = await kiStatus();
          ergebnisse.push({
            name: "LM Studio",
            icon: "fa-robot",
            status: ki.available ? "online" : "offline",
            info: ki.available ? `Modell: ${ki.model}` : "Nicht erreichbar",
            url: config.lm_studio.url,
          });
        } catch {
          ergebnisse.push({
            name: "LM Studio",
            icon: "fa-robot",
            status: "offline",
            info: "Nicht erreichbar",
            url: config.lm_studio.url,
          });
        }
      } else {
        ergebnisse.push({
          name: "LM Studio",
          icon: "fa-robot",
          status: "deaktiviert",
          info: "Deaktiviert",
          url: config.lm_studio?.url || null,
        });
      }
    }

    services = ergebnisse;
    laden = false;
  }

  const statusColors = {
    online: "var(--color-success)",
    offline: "var(--color-error)",
    deaktiviert: "var(--color-text-muted)",
  };
</script>

<div class="svc-list">
  {#if laden}
    <p class="svc-loading"><i class="fa-solid fa-spinner fa-spin"></i> Dienste werden geprüft...</p>
  {:else}
    {#each services as svc (svc.name)}
      <div class="svc-row">
        <span
          class="svc-dot"
          style="background-color: {statusColors[svc.status] || 'var(--color-text-muted)'}"
        ></span>
        <i class="fa-solid {svc.icon} svc-icon"></i>
        <span class="svc-name">{svc.name}</span>
        <span class="svc-info">{svc.info}</span>
        {#if svc.url}
          <code class="svc-url">{svc.url}</code>
        {/if}
      </div>
    {/each}
    <button class="svc-refresh" onclick={pruefeServices}>
      <i class="fa-solid fa-rotate"></i> Neu prüfen
    </button>
  {/if}
</div>

<style>
  .svc-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .svc-loading {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  .svc-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0;
    flex-wrap: wrap;
  }

  .svc-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .svc-icon {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    width: 1rem;
    text-align: center;
    flex-shrink: 0;
  }

  .svc-name {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--color-text-primary);
    min-width: 80px;
  }

  .svc-info {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .svc-url {
    font-size: 0.625rem;
    font-family: var(--font-mono);
    color: var(--color-text-secondary);
    background-color: var(--color-bg-primary);
    padding: 0.125rem 0.3125rem;
    border-radius: 3px;
    border: 1px solid var(--color-border);
    margin-left: auto;
  }

  .svc-refresh {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 5px;
    background: none;
    color: var(--color-text-muted);
    font-size: 0.625rem;
    cursor: pointer;
    margin-top: 0.25rem;
    align-self: flex-start;
    transition: all 0.1s;
  }

  .svc-refresh:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }
</style>
