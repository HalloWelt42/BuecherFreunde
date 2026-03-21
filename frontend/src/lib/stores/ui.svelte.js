/**
 * UI-Store: Theme, Ansichtsmodus, Sidebar-Status.
 */

function createUiStore() {
  const initialTheme = localStorage.getItem("theme") || "system";
  let theme = $state(initialTheme);
  let viewMode = $state(localStorage.getItem("viewMode") || "grid");
  let sidebarOpen = $state(true);
  let scratchPadOpen = $state(false);
  let readerFullscreen = $state(false);
  let bgBilder = $state([]);
  let bgIndex = $state(parseInt(localStorage.getItem("bgIndex") || "0", 10));

  const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function applyTheme(mode) {
    const root = document.documentElement;
    if (mode === "dark") {
      root.classList.add("dark");
    } else if (mode === "light") {
      root.classList.remove("dark");
    } else {
      root.classList.toggle("dark", mediaQuery.matches);
    }
  }

  function currentTheme() {
    return theme;
  }

  // Theme beim Start anwenden
  applyTheme(initialTheme);

  // Bei System-Theme-Wechsel automatisch aktualisieren
  mediaQuery.addEventListener("change", () => {
    if (currentTheme() === "system") {
      applyTheme("system");
    }
  });

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

    get scratchPadOpen() {
      return scratchPadOpen;
    },
    set scratchPadOpen(value) {
      scratchPadOpen = value;
    },
    toggleScratchPad() {
      scratchPadOpen = !scratchPadOpen;
    },

    get readerFullscreen() {
      return readerFullscreen;
    },
    set readerFullscreen(value) {
      readerFullscreen = value;
    },
    toggleReaderFullscreen() {
      readerFullscreen = !readerFullscreen;
    },

    // Hintergrundbilder
    get bgBilder() {
      return bgBilder;
    },
    set bgBilder(value) {
      bgBilder = value;
      // Index korrigieren falls Bilder entfernt wurden
      if (bgIndex >= value.length && value.length > 0) {
        bgIndex = 0;
        localStorage.setItem("bgIndex", "0");
      }
    },
    get bgIndex() {
      return bgIndex;
    },
    set bgIndex(value) {
      bgIndex = value;
      localStorage.setItem("bgIndex", String(value));
    },
    bgWeiter() {
      if (bgBilder.length <= 1) return;
      bgIndex = (bgIndex + 1) % bgBilder.length;
      localStorage.setItem("bgIndex", String(bgIndex));
    },
    bgZurueck() {
      if (bgBilder.length <= 1) return;
      bgIndex = (bgIndex - 1 + bgBilder.length) % bgBilder.length;
      localStorage.setItem("bgIndex", String(bgIndex));
    },
    get bgAktuellerDateiname() {
      if (bgBilder.length === 0) return null;
      const idx = Math.min(bgIndex, bgBilder.length - 1);
      return bgBilder[idx]?.dateiname || null;
    },

    cycleTheme() {
      const modes = ["light", "dark", "system"];
      const idx = modes.indexOf(theme);
      this.theme = modes[(idx + 1) % modes.length];
    },
  };
}

export const ui = createUiStore();
