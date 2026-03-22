<script>
  import { ui } from "../../stores/ui.svelte.js";
  import { get as apiGet } from "../../api/client.js";
  import { onMount } from "svelte";
  import SearchBar from "../search/SearchBar.svelte";
  import Bedanken from "../settings/Bedanken.svelte";

  const themeIcons = { light: "fa-sun", dark: "fa-moon", system: "fa-circle-half-stroke" };
  const themeLabels = { light: "Hell", dark: "Dunkel", system: "System" };

  let bedankenOpen = $state(false);

  onMount(async () => {
    try {
      const res = await apiGet("/api/config/design/hintergruende");
      ui.bgBilder = res.bilder || [];
    } catch {
      // still
    }
  });
</script>

<header class="app-header">
  <div class="header-left">
    <button
      class="header-btn sidebar-toggle"
      onclick={() => ui.toggleSidebar()}
      title="Seitenleiste {ui.sidebarOpen ? 'einklappen' : 'ausklappen'}"
    >
      <i class="fa-solid {ui.sidebarOpen ? 'fa-angles-left' : 'fa-angles-right'}"></i>
    </button>
    <a href="/" class="app-brand">
      <i class="fa-solid fa-book-open brand-icon"></i>
      <span class="brand-text">BücherFreunde</span>
    </a>
    <button class="donate-heart" onclick={() => bedankenOpen = true} title="Unterstützen">
      <i class="fa-solid fa-heart"></i>
    </button>
  </div>

  <div class="header-center">
    <SearchBar />
  </div>

  <div class="header-right">
    {#if ui.bgBilder.length > 1}
      <div class="bg-switcher">
        <button
          class="header-btn"
          onclick={() => ui.bgZurueck()}
          title="Vorheriges Hintergrundbild"
        >
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <span class="bg-counter">{ui.bgIndex + 1}/{ui.bgBilder.length}</span>
        <button
          class="header-btn"
          onclick={() => ui.bgWeiter()}
          title="Nächstes Hintergrundbild"
        >
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    {/if}
    <button
      class="header-btn"
      onclick={() => ui.cycleTheme()}
      title="Theme: {themeLabels[ui.theme]}"
    >
      <i class="fa-solid {themeIcons[ui.theme]}"></i>
    </button>
  </div>
</header>

<Bedanken bind:visible={bedankenOpen} />

<style>
  .app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 1rem;
    height: var(--header-height);
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border-bottom: 1px solid var(--glass-border);
    gap: 1rem;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
  }

  .header-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: none;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 0.875rem;
    text-decoration: none;
    transition: background-color 0.12s, color 0.12s, border-color 0.12s;
  }

  .header-btn:hover {
    background: var(--glass-bg-btn);
    backdrop-filter: blur(var(--glass-blur-btn));
    color: var(--color-text-primary);
    border-color: var(--glass-border);
  }

  .app-brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    white-space: nowrap;
  }

  .brand-icon {
    font-size: 1rem;
    color: var(--color-accent);
  }

  .brand-text {
    font-size: 0.9375rem;
    font-weight: 700;
    color: var(--color-text-primary);
    letter-spacing: -0.01em;
  }

  @keyframes heartPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.15); }
  }

  .donate-heart {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    font-size: 14px;
    color: #cc2244;
    text-shadow:
      0 0 6px rgba(204, 34, 68, 0.6),
      0 0 12px rgba(204, 34, 68, 0.3);
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
    transition: all 0.2s ease;
    animation: heartPulse 2s ease-in-out infinite;
  }

  .donate-heart:hover {
    color: #ee3355;
    text-shadow:
      0 0 10px rgba(238, 51, 85, 0.8),
      0 0 20px rgba(238, 51, 85, 0.5),
      0 0 30px rgba(238, 51, 85, 0.3);
    transform: scale(1.2);
    animation: none;
  }

  .donate-heart:active {
    transform: scale(0.95);
  }

  .header-center {
    flex: 1;
    max-width: 600px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-shrink: 0;
  }

  .bg-switcher {
    display: flex;
    align-items: center;
    gap: 0.125rem;
    margin-right: 0.25rem;
    padding-right: 0.5rem;
    border-right: 1px solid var(--glass-border);
  }

  .bg-counter {
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    min-width: 2rem;
    text-align: center;
  }
</style>
