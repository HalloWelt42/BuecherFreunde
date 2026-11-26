// Eigenes Kontextmenü überall in der App (BF-42): Rechtsklick und, wo der Browser es meldet, langes Drücken zeigen statt
// des Menüs des Browsers die Einträge des Bausteins darunter. Eingabefelder, Textfelder und der Editor behalten das Menü
// des Browsers (Einfügen, Rechtschreibung). Gezeigt wird mit dem Menü der App (lib/teile/Kontextmenue.svelte), das wie
// jedes Feld mit Esc und einem Druck daneben zugeht (lib/flucht.ts).
import type { Component } from "svelte";
import { kopiere } from "../kopieren";
import { navigate } from "../router.svelte";

export interface Eintrag {
  text: string;
  symbol: string;
  tun?: () => unknown;
  gesperrt?: boolean;
  /** Statt etwas zu tun, zeigt der Eintrag einen zweiten Schritt im selben Menü (etwa die Regale zur Wahl) */
  weiter?: { komponente: Component<any>; eigenschaften: Record<string, unknown> };
}

/** Was ein Baustein an dieser Stelle anbietet. "eigen": er zeigt selbst ein Menü (das Auswahlmenü im Leser), null: nichts */
export type Angebot = Eintrag[] | Promise<Eintrag[]> | "eigen" | null;
export type Anbieter = (e: MouseEvent, finger: boolean) => Angebot;

const anbieter = new WeakMap<Element, Anbieter>();

/** Svelte-Aktion: dieser Baustein bietet ein Kontextmenü an; es gilt der nächste Baustein über dem Ziel */
export function kontext(knoten: HTMLElement, a: Anbieter) {
  anbieter.set(knoten, a);
  return {
    update: (neu: Anbieter) => void anbieter.set(knoten, neu),
    destroy: () => void anbieter.delete(knoten),
  };
}

class Kontextmenue {
  offen = $state.raw<{ x: number; y: number; eintraege: Eintrag[] } | null>(null);

  zeige(x: number, y: number, eintraege: Eintrag[]): void {
    this.offen = eintraege.length ? { x, y, eintraege } : null;
  }

  schliesse(): void {
    this.offen = null;
  }
}

export const kontextmenue = new Kontextmenue();

// Hier gilt das Menü des Browsers
const DES_BROWSERS = "input, textarea, select, [contenteditable=''], [contenteditable='true'], .cm-editor";

/** Elemente auch aus dem Rahmen eines Kapitels (anderes Fenster, darum ohne instanceof) */
function elementVon(ziel: EventTarget | null): Element | null {
  const k = ziel as Node | null;
  return !k ? null : k.nodeType === Node.ELEMENT_NODE ? (k as Element) : k.parentElement;
}

/** Ohne eigenen Baustein: markierter Text zum Kopieren, ein Verweis zum Öffnen */
function allgemein(e: MouseEvent, ziel: Element | null): Angebot {
  const text = (e.view ?? window).getSelection()?.toString().trim() ?? "";
  if (text) return [{ text: "Kopieren", symbol: "copy", tun: () => kopiere(text) }];
  const verweis = ziel?.closest<HTMLAnchorElement>("a[href]");
  if (!verweis) return null;
  const adresse = verweis.href;
  const hier = new URL(adresse, location.href).origin === location.origin && !verweis.getAttribute("href")?.startsWith("/api/");
  return [
    { text: "Öffnen", symbol: "arrow-right", tun: () => (hier ? navigate(new URL(adresse).pathname + new URL(adresse).search) : open(adresse, "_blank", "noopener")) },
    { text: "In neuem Tab öffnen", symbol: "arrow-up-right-from-square", tun: () => open(adresse, "_blank", "noopener") },
    { text: "Adresse kopieren", symbol: "link", tun: () => kopiere(adresse) },
  ];
}

function finde(start: Element | null): Anbieter | null {
  for (let e = start; e; e = e.parentElement) {
    const a = anbieter.get(e);
    if (a) return a;
  }
  return null;
}

/** Was vor dem Druck der rechten Taste gewählt war; manche Browser wählen dabei selbst das Wort unter der Maus */
const zuvorGewaehlt = new WeakMap<Document, { text: string; zeit: number }>();

async function beiKontext(e: MouseEvent, gast: (() => Element | null) | undefined): Promise<void> {
  const ziel = elementVon(e.target);
  if (ziel?.closest(DES_BROWSERS)) return;
  // Das Wort, das erst der Rechtsklick gewählt hat, ist keine Auswahl des Lesers
  const auswahl = (e.view ?? window).getSelection();
  const dok = (e.target as Node | null)?.ownerDocument ?? document;
  const zuvor = zuvorGewaehlt.get(dok);
  if (auswahl && !auswahl.isCollapsed && zuvor && !zuvor.text && Date.now() - zuvor.zeit < 1500) auswahl.removeAllRanges();
  const finger = (e as PointerEvent).pointerType === "touch" || !!(e as MouseEvent & { sourceCapabilities?: { firesTouchEvents?: boolean } }).sourceCapabilities?.firesTouchEvents;
  const traeger = gast?.() ?? ziel;
  const a = finde(traeger);
  const angebot = a ? a(e, finger) : allgemein(e, ziel);
  // Langes Drücken ohne Angebot gehört dem Browser (Auswahl im Text); die Maus bekommt nie sein Menü
  if (angebot === null && finger) return;
  e.preventDefault();
  if (angebot === null || angebot === "eigen") return;
  const rahmen = gast ? (e.view?.frameElement?.getBoundingClientRect() ?? null) : null;
  const [x, y] = [e.clientX + (rahmen?.left ?? 0), e.clientY + (rahmen?.top ?? 0)];
  kontextmenue.zeige(x, y, await angebot);
}

const beobachtet = new WeakSet<Document>();

/** Ein Dokument, in dem das eigene Menü gilt; gast: im Rahmen eines Kapitels der Baustein draußen, der dafür anbietet */
export function beobachteKontext(dok: Document, gast?: () => Element | null): void {
  if (beobachtet.has(dok)) return;
  beobachtet.add(dok);
  dok.addEventListener("mousedown", (e) => e.button === 2 && zuvorGewaehlt.set(dok, { text: dok.getSelection()?.toString() ?? "", zeit: Date.now() }), true);
  dok.addEventListener("contextmenu", (e) => void beiKontext(e, gast));
}

if (typeof document !== "undefined") beobachteKontext(document);
