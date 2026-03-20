<script>
  import { kiStatus, healthCheck, ladeConfig } from "../../api/config.js";

  let services = $state([]);
  let laden = $state(true);

  $effect(() => {
    pruefeServices();
  });

  async function pruefeServices() {
    laden = true;
    const ergebnisse = [];

    // Backend
    try {
      const health = await healthCheck();
      ergebnisse.push({
        name: "Backend",
        status: "online",
        info: `v${health.version}`,
      });
    } catch {
      ergebnisse.push({ name: "Backend", status: "offline", info: "Nicht erreichbar" });
    }

    // Konfiguration laden
    try {
      const config = await ladeConfig();

      // Open Library
      ergebnisse.push({
        name: "Open Library",
        status: config.openlibrary_enabled ? "online" : "deaktiviert",
        info: config.openlibrary_enabled ? "Aktiviert" : "Deaktiviert",
      });

      // LM Studio
      if (config.lm_studio_enabled) {
        try {
          const ki = await kiStatus();
          ergebnisse.push({
            name: "LM Studio",
            status: ki.available ? "online" : "offline",
            info: ki.available ? `Modell: ${ki.model}` : "Nicht erreichbar",
          });
        } catch {
          ergebnisse.push({
            name: "LM Studio",
            status: "offline",
            info: "Nicht erreichbar",
          });
        }
      } else {
        ergebnisse.push({
          name: "LM Studio",
          status: "deaktiviert",
          info: "Deaktiviert",
        });
      }
    } catch { /* still */ }

    services = ergebnisse;
    laden = false;
  }

  const statusColors = {
    online: "var(--color-success)",
    offline: "var(--color-error)",
    deaktiviert: "var(--color-text-muted)",
  };
</script>

<div class="service-list">
  {#if laden}
    <p class="info">Dienste werden geprüft...</p>
  {:else}
    {#each services as service (service.name)}
      <div class="service-item">
        <span
          class="status-dot"
          style="background-color: {statusColors[service.status] || 'var(--color-text-muted)'}"
        ></span>
        <span class="service-name">{service.name}</span>
        <span class="service-info">{service.info}</span>
      </div>
    {/each}
  {/if}
</div>

<style>
  .service-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .info {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
  }

  .service-item {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.5rem 0;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .service-name {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
  }

  .service-info {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    margin-left: auto;
  }
</style>
