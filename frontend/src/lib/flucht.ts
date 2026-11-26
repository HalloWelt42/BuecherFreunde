// Esc schließt immer das zuletzt Geöffnete, genau eines je Druck. Offene Felder und Menüs schließt ebenso ein Druck
// daneben (BF-39), auch im Buchrahmen eines EPUB: die eine Regel für alle, hier an einer Stelle.
import { istBedienbar } from "./leser/bedienbar";

type Schliessen = () => void;

const stapel: Schliessen[] = [];

/** Anmelden, solange etwas offen ist; liefert das Abmelden. */
export function beiEsc(schliessen: Schliessen): () => void {
  stapel.push(schliessen);
  return () => {
    const n = stapel.lastIndexOf(schliessen);
    if (n >= 0) stapel.splice(n, 1);
  };
}

interface Feld {
  /** Was zum Feld zählt: das Feld selbst und was es öffnet und schließt (sein Knopf) */
  drinnen: () => readonly (Element | null | undefined)[];
  schliessen: Schliessen;
}

const felder: Feld[] = [];

/**
 * Ein offenes Feld oder Menü: Esc und ein Druck daneben schließen es, das zuletzt geöffnete zuerst und je Druck nur
 * eines. Ein Druck daneben schließt nur: er blättert nicht und tippt nichts im Buch an; trifft er einen Knopf, ein
 * Eingabefeld oder einen Verweis, tut der danach, was er soll. Die Auswahl im Text bleibt Sache des Browsers. Liefert
 * das Abmelden.
 */
export function offenesFeld(drinnen: Feld["drinnen"], schliessen: Schliessen): () => void {
  const feld: Feld = { drinnen, schliessen };
  felder.push(feld);
  const ab = beiEsc(schliessen);
  return () => {
    ab();
    const n = felder.lastIndexOf(feld);
    if (n >= 0) felder.splice(n, 1);
  };
}

/** So lange nach dem schließenden Druck gehören die übrigen Ereignisse desselben Tippens noch zu ihm */
const SCHLUCKEN_MS = 700;
/** Uhr des Hauptfensters: die Zeitstempel der Ereignisse zählen je Rahmen anders */
let schluckenBis = 0;

function druck(e: PointerEvent): void {
  const feld = felder.at(-1);
  if (!feld || e.button > 0) return;
  const ziel = e.target as Node | null;
  if (!ziel || feld.drinnen().some((d) => d?.contains(ziel))) return;
  feld.schliessen();
  if (istBedienbar(ziel)) return;
  e.stopPropagation();
  schluckenBis = Date.now() + SCHLUCKEN_MS;
}

// Was zum schließenden Druck gehört (Finger hoch, Klick), erreicht weder Blättern noch Tippzonen; der Klick beendet es
function schlucke(e: Event): void {
  if (Date.now() > schluckenBis) return;
  e.stopPropagation();
  if (e.type === "click") schluckenBis = 0;
}

function taste(e: KeyboardEvent): void {
  if (e.key !== "Escape" || e.defaultPrevented || !stapel.length) return;
  e.preventDefault();
  stapel[stapel.length - 1]();
}

const beobachtet = new WeakSet<Document>();

/** Ein weiteres Dokument, in dem ein Druck daneben gilt (der Rahmen eines Kapitels im EPUB; Esc reicht er selbst weiter) */
export function beobachteDokument(dok: Document): void {
  if (beobachtet.has(dok)) return;
  beobachtet.add(dok);
  const fenster = dok.defaultView;
  if (!fenster) return;
  fenster.addEventListener("pointerdown", druck, true);
  for (const art of ["pointerup", "touchstart", "touchend", "mousedown", "mouseup", "click"]) fenster.addEventListener(art, schlucke, true);
}

if (typeof document !== "undefined") {
  beobachteDokument(document);
  document.addEventListener("keydown", taste);
}

/** Liegt der Fokus in einem Feld, gehören ihm die Tasten. */
export function schreibtGerade(e: Event): boolean {
  const ziel = e.target instanceof HTMLElement ? e.target : null;
  return !!ziel && (ziel.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ziel.tagName));
}
