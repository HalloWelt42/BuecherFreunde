/**
 * UI-Store: Theme, Ansichtsmodus, Sidebar-Status.
 */

function createUiStore() {
  let theme = $state(localStorage.getItem("theme") || "system");
  let viewMode = $state(localStorage.getItem("viewMode") || "grid");
  let sidebarOpen = $state(true);

  // Theme beim Start anwenden
  applyTheme(theme);

  function applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "dark") {
      root.classList.add("dark");
    } else if (mode === "light") {
      root.classList.remove("dark");
    } else {
      // System
      const prefersDark = window.matchMedia(
        "(prefers-color-scheme: dark)",
      ).matches;
      root.classList.toggle("dark", prefersDark);
    }
  }

  return {
    get theme() {
      return theme;
    },
    set theme(value) {
      theme = value;
      localStorage.setItem("theme", value);
      applyTheme(value);
    },

    get viewMode() {
      return viewMode;
    },
    set viewMode(value) {
      viewMode = value;
      localStorage.setItem("viewMode", value);
    },

    get sidebarOpen() {
      return sidebarOpen;
    },
    set sidebarOpen(value) {
      sidebarOpen = value;
    },

    toggleSidebar() {
      sidebarOpen = !sidebarOpen;
    },

    cycleTheme() {
      const modes = ["light", "dark", "system"];
      const idx = modes.indexOf(theme);
      this.theme = modes[(idx + 1) % modes.length];
    },
  };
}

export const ui = createUiStore();
