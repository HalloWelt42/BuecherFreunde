// Zeichen für Regale, mit deutschen Stichworten für die Suche
export const symbole: [string, string][] = [
  ["fa-book", "Buch"], ["fa-book-open", "Buch offen lesen"], ["fa-book-bookmark", "Buch Lesezeichen"], ["fa-book-atlas", "Atlas"],
  ["fa-file", "Datei Blatt"], ["fa-file-lines", "Datei Text Dokument"], ["fa-file-pdf", "Datei PDF"], ["fa-file-code", "Datei Quelltext"],
  ["fa-scroll", "Schriftrolle Geschichte"], ["fa-newspaper", "Zeitung Zeitschrift"], ["fa-bookmark", "Lesezeichen"],
  ["fa-graduation-cap", "Studium Doktorhut Ausbildung"], ["fa-microscope", "Mikroskop Forschung Biologie"], ["fa-flask", "Kolben Chemie Wissenschaft"], ["fa-atom", "Atom Physik"],
  ["fa-brain", "Gehirn Psychologie"], ["fa-lightbulb", "Glühbirne Idee"], ["fa-chalkboard", "Tafel Unterricht"], ["fa-school", "Schule"],
  ["fa-laptop-code", "Laptop Programmieren"], ["fa-microchip", "Chip Technik Elektronik"], ["fa-robot", "Roboter KI"], ["fa-code", "Quelltext Programmieren"],
  ["fa-database", "Datenbank"], ["fa-server", "Server"], ["fa-network-wired", "Netzwerk"], ["fa-terminal", "Konsole Terminal"],
  ["fa-folder", "Ordner"], ["fa-folder-open", "Ordner offen"], ["fa-tag", "Schild Etikett"], ["fa-tags", "Schilder Kataloge"],
  ["fa-layer-group", "Stapel Ebenen"], ["fa-boxes-stacked", "Kisten Lager"], ["fa-sitemap", "Aufbau Gliederung"], ["fa-list", "Liste"],
  ["fa-globe", "Welt Netz"], ["fa-earth-americas", "Erde Erdkunde"], ["fa-leaf", "Blatt Natur"], ["fa-tree", "Baum Wald"],
  ["fa-mountain-sun", "Berg Landschaft"], ["fa-water", "Wasser Meer"], ["fa-sun", "Sonne"], ["fa-moon", "Mond Nacht"],
  ["fa-user", "Person"], ["fa-users", "Personen Gruppe"], ["fa-children", "Kinder"], ["fa-people-group", "Menschen Gesellschaft"],
  ["fa-handshake", "Handschlag Geschäft"], ["fa-comments", "Gespräch"], ["fa-message", "Nachricht"], ["fa-heart", "Herz Liebe"],
  ["fa-palette", "Farben Kunst Malerei"], ["fa-paintbrush", "Pinsel Malen"], ["fa-camera", "Kamera Foto"], ["fa-film", "Film Kino"],
  ["fa-music", "Musik Noten"], ["fa-guitar", "Gitarre"], ["fa-masks-theater", "Theater Masken"], ["fa-pen-fancy", "Feder Schreiben"],
  ["fa-feather", "Feder Romane"], ["fa-futbol", "Fußball Sport"], ["fa-dumbbell", "Hantel Sport"], ["fa-bicycle", "Fahrrad"], ["fa-chess", "Schach"],
  ["fa-gamepad", "Spiele"], ["fa-puzzle-piece", "Puzzle Rätsel"], ["fa-dice", "Würfel"], ["fa-trophy", "Pokal"],
  ["fa-heart-pulse", "Gesundheit Puls"], ["fa-stethoscope", "Arzt Medizin"], ["fa-pills", "Tabletten"], ["fa-hospital", "Krankenhaus"],
  ["fa-scale-balanced", "Waage Recht Philosophie"], ["fa-landmark", "Denkmal Geschichte"], ["fa-building-columns", "Säulen Verwaltung"], ["fa-chart-line", "Kurve Statistik"],
  ["fa-coins", "Münzen Geld"], ["fa-briefcase", "Aktentasche Beruf"], ["fa-gavel", "Hammer Gericht"], ["fa-receipt", "Beleg Rechnung"],
  ["fa-hammer", "Hammer Handwerk"], ["fa-screwdriver-wrench", "Werkzeug Reparatur"], ["fa-cross", "Kreuz"], ["fa-star-and-crescent", "Halbmond"], ["fa-om", "Om"], ["fa-yin-yang", "Yin Yang"],
  ["fa-dove", "Taube Frieden"], ["fa-pray", "Gebet"], ["fa-place-of-worship", "Gotteshaus"], ["fa-church", "Kirche"],
  ["fa-plane", "Flugzeug Reise"], ["fa-ship", "Schiff"], ["fa-car", "Auto"], ["fa-train", "Zug Bahn"],
  ["fa-map", "Karte"], ["fa-compass", "Kompass"], ["fa-route", "Weg Strecke"], ["fa-location-dot", "Ort"],
  ["fa-utensils", "Besteck Kochen"], ["fa-bread-slice", "Brot Backen"], ["fa-mug-hot", "Tasse Kaffee"], ["fa-wine-glass", "Wein"], ["fa-apple-whole", "Apfel Obst"],
  ["fa-star", "Stern"], ["fa-fire", "Feuer"], ["fa-bolt", "Blitz Strom"], ["fa-shield", "Schild Schutz"],
  ["fa-crown", "Krone"], ["fa-gem", "Edelstein"], ["fa-key", "Schlüssel"], ["fa-lock", "Schloss"],
  ["fa-wand-magic-sparkles", "Zauberstab"], ["fa-hat-wizard", "Zauberhut Fantasie"], ["fa-dragon", "Drache Fantasie"], ["fa-ghost", "Geist Grusel"],
];

/** Sucht in Stichworten und im Namen des Zeichens */
export function findeSymbole(wort: string): [string, string][] {
  const w = wort.trim().toLowerCase();
  return w ? symbole.filter(([name, stichworte]) => name.includes(w) || stichworte.toLowerCase().includes(w)) : symbole;
}
