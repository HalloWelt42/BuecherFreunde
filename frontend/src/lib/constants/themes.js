/**
 * Zentrale Reader-Farbthemen und Schriftarten.
 * Verwendet von EpubReader, MarkdownReader.
 */

export const readerFarbThemen = [
  { name: "Hell", fg: "#1a1a1a", bg: "#ffffff", icon: "fa-sun" },
  { name: "Sepia", fg: "#3d2b1f", bg: "#f4ecd8", icon: "fa-cloud-sun" },
  { name: "Daemmerung", fg: "#c9b99a", bg: "#3d3526", icon: "fa-cloud-moon" },
  { name: "Dunkel", fg: "#c8c8c8", bg: "#1e1e1e", icon: "fa-moon" },
  { name: "Nacht", fg: "#8a8a8a", bg: "#0a0a0a", icon: "fa-star" },
];

export const readerSchriften = [
  { name: "Standard", value: "" },
  { name: "Barlow", value: "Barlow, sans-serif" },
  { name: "JetBrains Mono", value: "'JetBrains Mono', monospace" },
  { name: "Serif", value: "Georgia, 'Times New Roman', serif" },
  { name: "System", value: "system-ui, -apple-system, sans-serif" },
];
