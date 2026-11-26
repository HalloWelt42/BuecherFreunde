// Wohin Bücher von Hand kommen (BF-67): in eine Sammlung (mit Bandnummer und Reihenfolge), in ein Regal (ohne) oder in die
// Freigaben eines Kindes (BF-78). Die Ansicht kennt nur diese Schnittstelle; was je Art anders ist, steht hier und nur hier.
import { bulkAction } from "../../lib/api/books";
import type { Parameter } from "../../lib/api/client";
import { setzeReihenfolge } from "../../lib/api/collections";
import { gibFrei, ladeFreigaben, nimmFreigabe } from "../../lib/api/familie";
import { alterHinweis, alterText } from "../../lib/familie";
import { anzahl } from "../../lib/format";
import { bestand } from "../../lib/stand/bestand.svelte";
import { familie } from "../../lib/stand/familie.svelte";
import type { Buch, BuchListe } from "../../lib/typen";

export type Zielart = "sammlung" | "regal" | "freigabe";

export interface Zuordnungsziel {
  art: Zielart;
  /** Nummer der Sammlung oder des Regals, Kennung des Profils */
  id: number | string;
  /** Name für die Taste zurück; leer, solange er nicht geladen ist */
  name(): string;
  /** Linke Spalte, am Telefon auch der Umschalter */
  drinText: string;
  /** Wohin es zurückgeht */
  zurueck: string;
  /** Filter der Bücher, die drin sind, mit ihrer Ordnung */
  drin: Parameter;
  /** Kommt das, was drin ist, nicht aus der Liste der Bücher, holt es diese Quelle auf einmal */
  drinQuelle?: () => Promise<BuchListe>;
  /** Was rechts an jeder Zeile steht, mit Hinweis, etwa die Altersangabe beim Freigeben */
  merkmal?: (buch: Buch) => { text: string; titel: string };
  /** Filter des Bestands, also allem, was nicht drin ist; ohneSammlung: nur Bücher ohne Sammlung */
  uebrig(ohneSammlung: boolean): Parameter;
  /** Steht das Buch schon drin? Der Bestand einer Sammlung ohne den Schalter "Ohne Sammlung" enthält sie sonst mit */
  hat(buch: Buch): boolean;
  dazu(ids: number[]): Promise<unknown>;
  heraus(ids: number[]): Promise<unknown>;
  /** Nur, wo es eine Reihenfolge gibt (Sammlung): Bandnummern 1 bis n in dieser Folge */
  ordne?: (ids: number[]) => Promise<unknown>;
  /** Das Buch, wie es nach dem Herausnehmen ist (bis der Server es neu schickt) */
  ohne(buch: Buch): Buch;
  /** Was das Hineinnehmen anderswo nimmt, für die Rückfrage; leer: nichts, keine Frage */
  folgenDazu(buecher: Buch[]): string[];
  /** Was beim Herausnehmen von n Büchern verloren geht, für die Rückfrage */
  folgenHeraus(n: number): string[];
  /** Was rechts steht, in Worten */
  bestandText(ohneSammlung: boolean): string;
  /** Vorgabe des Schalters "Ohne Sammlung" */
  ohneSammlungVorgabe: boolean;
  /** Vorgabe des Schalters "Gleicher Autor" */
  gleicherAutorVorgabe: boolean;
}

/** n Bücher: "Das Buch ..." oder "Die Bücher ..." */
const bleiben = (n: number): string => (n === 1 ? "Das Buch selbst bleibt in der Bibliothek." : "Die Bücher selbst bleiben in der Bibliothek.");

/** Ein Buch steht in höchstens einer Sammlung: wer aus einer anderen kommt, verlässt sie samt Bandnummer */
function andereSammlungen(buecher: Buch[], id: number): string[] {
  const woher = new Map<string, number>();
  for (const b of buecher) {
    if (!b.sammlung_id || b.sammlung_id === id) continue;
    const name = b.sammlung?.name ? `die Sammlung ${b.sammlung.name}` : "ihre bisherige Sammlung";
    woher.set(name, (woher.get(name) ?? 0) + 1);
  }
  if (!woher.size) return [];
  return [...[...woher].map(([name, n]) => `${anzahl(n, "Buch verlässt", "Bücher verlassen")} ${name} samt Bandnummer.`), bleiben(buecher.length)];
}

export function sammlungsziel(id: number): Zuordnungsziel {
  return {
    art: "sammlung",
    id,
    name: () => bestand.sammlung(id)?.name ?? "",
    drinText: "In der Sammlung",
    zurueck: `/collection/${id}`,
    drin: { sammlung: id, sortierung: "band", richtung: "asc" },
    uebrig: (ohneSammlung) => ({ ohne_sammlung: ohneSammlung || undefined, sortierung: "titel", richtung: "asc" }),
    hat: (b) => b.sammlung_id === id,
    // Neue Bände kommen hinten an
    dazu: (ids) => bulkAction(ids, "sammlung_zuweisen", id),
    heraus: (ids) => bulkAction(ids, "sammlung_entfernen", null),
    ordne: (ids) => setzeReihenfolge(id, ids),
    ohne: (b) => ({ ...b, sammlung_id: null, sammlung: null, band_nummer: "" }),
    folgenDazu: (buecher) => andereSammlungen(buecher, id),
    folgenHeraus: (n) => [n === 1 ? "Das Buch verliert die Sammlung und seine Bandnummer." : "Die Bücher verlieren die Sammlung und ihre Bandnummer.", bleiben(n)],
    bestandText: (ohneSammlung) => (ohneSammlung ? "ohne Sammlung" : "auch aus anderen Sammlungen"),
    ohneSammlungVorgabe: true,
    gleicherAutorVorgabe: true,
  };
}

export function regalziel(id: number): Zuordnungsziel {
  return {
    art: "regal",
    id,
    name: () => bestand.regal(id)?.name ?? "",
    drinText: "Im Regal",
    zurueck: `/?category=${id}`,
    drin: { kategorie: id, sortierung: "titel", richtung: "asc" },
    uebrig: (ohneSammlung) => ({ nicht_kategorie: id, ohne_sammlung: ohneSammlung || undefined, sortierung: "titel", richtung: "asc" }),
    hat: (b) => b.categories.some((c) => c.id === id),
    dazu: (ids) => bulkAction(ids, "kategorie_zuweisen", id),
    heraus: (ids) => bulkAction(ids, "kategorie_entfernen", id),
    ohne: (b) => ({ ...b, categories: b.categories.filter((c) => c.id !== id) }),
    // Ein Buch darf in vielen Regalen stehen: hineinstellen nimmt nirgends etwas weg
    folgenDazu: () => [],
    folgenHeraus: (n) => [n === 1 ? "Das Buch verlässt dieses Regal, andere Regale behalten es." : "Die Bücher verlassen dieses Regal, andere Regale behalten sie.", bleiben(n)],
    bestandText: (ohneSammlung) => (ohneSammlung ? "nicht im Regal, ohne Sammlung" : "nicht im Regal"),
    ohneSammlungVorgabe: false,
    gleicherAutorVorgabe: false,
  };
}

/** Was ein Kind sieht (BF-78): links die einzeln freigegebenen Bücher, rechts alle anderen, je mit der Altersangabe */
export function freigabeziel(profil: string): Zuordnungsziel {
  const kind = () => familie.profil(profil)?.name ?? "";
  const das = (n: number) => (n === 1 ? "das Buch" : "die Bücher");
  return {
    art: "freigabe",
    id: profil,
    name: kind,
    drinText: "Freigegeben",
    zurueck: `/settings/familie/${encodeURIComponent(profil)}`,
    drin: {},
    drinQuelle: async () => {
      const { buecher } = await ladeFreigaben(profil);
      return { buecher, gesamt: buecher.length, seite: 1, pro_seite: buecher.length, seiten_gesamt: 1 };
    },
    merkmal: (b) => ({ text: alterText(b), titel: alterHinweis(b) || "Keine Altersangabe" }),
    uebrig: (ohneSammlung) => ({ ohne_sammlung: ohneSammlung || undefined, sortierung: "titel", richtung: "asc" }),
    // Was links steht, nimmt die Zuordnung rechts selbst heraus
    hat: () => false,
    dazu: (ids) => gibFrei(profil, "buch", ids),
    heraus: (ids) => nimmFreigabe(profil, "buch", ids),
    ohne: (b) => b,
    // Freigeben nimmt nirgends etwas weg
    folgenDazu: () => [],
    folgenHeraus: (n) => [`${kind() || "Das Kind"} sieht ${das(n)} danach nur noch, wenn eine freigegebene Kategorie ${n === 1 ? "es" : "sie"} enthält.`, bleiben(n)],
    bestandText: (ohneSammlung) => (ohneSammlung ? "nicht freigegeben, ohne Sammlung" : "nicht freigegeben"),
    ohneSammlungVorgabe: false,
    gleicherAutorVorgabe: false,
  };
}

/** Aus der Adresse /zuordnen/:art/:id; unbekannte Art oder Nummer: null */
export function zielAus(art: string, id: string): Zuordnungsziel | null {
  if (art === "freigabe") return id ? freigabeziel(id) : null;
  const nummer = Number(id);
  if (!Number.isInteger(nummer) || nummer <= 0) return null;
  return art === "sammlung" ? sammlungsziel(nummer) : art === "regal" ? regalziel(nummer) : null;
}
