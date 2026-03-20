<script>
  let version = $state("...");

  async function ladeVersion() {
    try {
      const res = await fetch("/api/config/version");
      if (res.ok) {
        const data = await res.json();
        version = data.version;
      }
    } catch {
      version = "offline";
    }
  }

  $effect(() => {
    ladeVersion();
  });
</script>

<div class="app-layout">
  <header class="app-header">
    <div class="header-left">
      <h1 class="app-title">BuecherFreunde</h1>
    </div>
    <div class="header-center">
      <input
        type="search"
        placeholder="Buecher durchsuchen..."
        class="search-input"
      />
    </div>
    <div class="header-right">
      <button class="theme-toggle" title="Theme wechseln">
        &#9789;
      </button>
    </div>
  </header>

  <aside class="app-sidebar">
    <nav class="sidebar-nav">
      <p class="sidebar-placeholder">Kategorien werden geladen...</p>
    </nav>
  </aside>

  <main class="app-main">
    <div class="main-placeholder">
      <h2>Willkommen bei BuecherFreunde</h2>
      <p>Die Bibliothek wird eingerichtet. Bitte ein Buch importieren.</p>
    </div>
  </main>

  <footer class="app-footer">
    <span>BuecherFreunde v{version}</span>
  </footer>
</div>

<style>
  .app-layout {
    display: grid;
    grid-template-areas:
      "header header"
      "sidebar main"
      "footer footer";
    grid-template-columns: var(--sidebar-width) 1fr;
    grid-template-rows: var(--header-height) 1fr auto;
    min-height: 100vh;
  }

  .app-header {
    grid-area: header;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1rem;
    background-color: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
    gap: 1rem;
  }

  .app-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-accent);
    white-space: nowrap;
  }

  .header-center {
    flex: 1;
    max-width: 600px;
  }

  .search-input {
    width: 100%;
    padding: 0.5rem 1rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background-color: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-family: var(--font-sans);
    font-size: 0.875rem;
  }

  .search-input:focus {
    outline: 2px solid var(--color-accent);
    outline-offset: -1px;
  }

  .theme-toggle {
    background: none;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    cursor: pointer;
    font-size: 1.1rem;
    color: var(--color-text-secondary);
  }

  .theme-toggle:hover {
    background-color: var(--color-bg-tertiary);
  }

  .app-sidebar {
    grid-area: sidebar;
    background-color: var(--color-bg-secondary);
    border-right: 1px solid var(--color-border);
    padding: 1rem;
    overflow-y: auto;
  }

  .sidebar-placeholder {
    color: var(--color-text-muted);
    font-size: 0.875rem;
  }

  .app-main {
    grid-area: main;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .main-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--color-text-secondary);
    text-align: center;
    gap: 0.5rem;
  }

  .main-placeholder h2 {
    font-size: 1.5rem;
    font-weight: 600;
  }

  .app-footer {
    grid-area: footer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
    background-color: var(--color-bg-secondary);
    border-top: 1px solid var(--color-border);
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
</style>
