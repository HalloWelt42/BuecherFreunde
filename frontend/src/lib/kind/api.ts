// Wege, die nur der Kinderbereich braucht (docs/neubau/FAMILIE.md, Schnittstelle). Profil, Katze und Verlassen gehen über
// lib/api/familie.ts und den Stand lib/stand/ich.svelte.ts; welche Bücher ein Kind sieht, entscheidet der Server.
import { anfrage } from "../api/client";
import { listeBooks } from "../api/books";
import { lesezeitAus } from "./ich";
import type { Buch } from "../typen";
import type { Lesezeitstand } from "./typen";

/** Gelesene Sekunden seit der letzten Meldung; vorlesen: es wurde vorgelesen. beimGehen: geht auch noch hinaus, wenn die Seite
 *  gerade zugeht. Die Antwort ist der neue Stand. */
export async function meldeLesezeit(sekunden: number, vorlesen: boolean, beimGehen = false): Promise<Lesezeitstand> {
  const antwort = await anfrage("/api/familie/lesezeit", { method: "POST", body: JSON.stringify({ sekunden, vorlesen }), keepalive: beimGehen });
  return lesezeitAus(await antwort.json().catch(() => ({})));
}

export type Regalart = "alle" | "lieblinge" | "gelesen";

const PRO_SEITE = 100;

/** Alle Bücher, die das Kind sehen darf, Seite für Seite geholt; der Server lässt nur Freigegebenes durch. "gelesen": die fertig
 *  gelesenen nach der Regel des Servers (fertig_am) */
export async function holeRegal(art: Regalart): Promise<Buch[]> {
  const filter = art === "lieblinge" ? { favorit: true } : art === "gelesen" ? { gelesen: true } : {};
  const aus: Buch[] = [];
  for (let seite = 1; ; seite++) {
    const liste = await listeBooks({ ...filter, seite, pro_seite: PRO_SEITE });
    aus.push(...liste.buecher);
    if (seite >= liste.seiten_gesamt || !liste.buecher.length) return aus;
  }
}
