// Welches Muster in welchen Farben (BF-59): Dokumente, Hefte, Kataloge und Broschüren nach ihrer Art, Bücher nach ihrer
// Gattung, alles wie in der Stilprobe. Mehrere Farbsätze wechseln nach der Nummer des Buchs; die Schlüssel sind die
// Kennungen des Servers (GET /api/collections/typen und /gattungen). Als Map, damit Schlüssel wie "constructor" nichts finden.
import type { Dreiklang } from "../farben";
import type { Mustername } from "./muster";

/** Wie das Blatt im Rahmen steht: gebunden mit Falz und Lichtkante, oder flach und kantig wie ein Aktenordner (BF-70) */
export type Form = "buch" | "ordner";

export interface Gestalt {
  muster: Mustername;
  farben: Dreiklang[];
  form?: Form;
}

const ARTEN = new Map<string, Gestalt>(Object.entries({
  dokument: { muster: "ordnerRuecken", form: "ordner", farben:[["#22384f", "#f6f3ea", "#1d2228"], ["#59636d", "#f6f3ea", "#1d2228"], ["#8a2c23", "#f6f3ea", "#1d2228"], ["#2f5a43", "#f6f3ea", "#1d2228"]] },
  heft: { muster: "heft", farben: [["#b3402a", "#f0e3c4", "#20323b"], ["#2c4a63", "#e7dfc8", "#d86a2a"]] },
  katalog: { muster: "katalog", farben: [["#e9e2d0", "#c4572e", "#253646"], ["#e4eadf", "#4f8a3c", "#23332b"]] },
  broschuere: { muster: "broschuere", farben: [["#f3efe6", "#c4572e", "#253646"], ["#eef2f5", "#2f6d7a", "#1d2a33"]] },
} satisfies Record<string, Gestalt>));

const GATTUNGEN = new Map<string, Gestalt>(Object.entries({
  krimi: { muster: "teilung", farben: [["#16161a", "#8e1b22", "#f3e9dc"]] },
  thriller: { muster: "kreis", farben: [["#12191f", "#7c8b95", "#e9e4da"]] },
  historisch: { muster: "leinen", farben: [["#6b1f2b", "#8c3040", "#d9b56a"], ["#2f3b33", "#4a5c4f", "#c9b26b"]] },
  fantasy: { muster: "sterne", farben: [["#0c1a3a", "#274a8f", "#f4e6b0"]] },
  liebesroman: { muster: "wellen", farben: [["#2b3f4c", "#6f93a3", "#e8e2cf"]] },
  roman: { muster: "berge", farben: [["#12202b", "#3f5d63", "#c9e0b8"]] },
  klassiker: { muster: "typo", farben: [["#1d1d1b", "#8fa31e", "#f3f0e4"]] },
  sachbuch: { muster: "globus", farben: [["#14484a", "#e0a33a", "#f2ead2"]] },
  ratgeber: { muster: "blatt", farben: [["#33632f", "#7fae4d", "#f5f0d8"]] },
  informatik: { muster: "schaltung", farben: [["#123a52", "#2f8fb3", "#f2c14e"]] },
  mathematik: { muster: "raster", farben: [["#1f2f6b", "#5f7be0", "#f4f6ff"]] },
  fachbuch: { muster: "kreis", farben: [["#0e2b2b", "#37b39a", "#f4efe2"]] },
  wirtschaft: { muster: "teilung", farben: [["#0f5a50", "#1f9a82", "#f6f1e1"]] },
} satisfies Record<string, Gestalt>));

/** Buch ohne Gattung: nur Schrift, ruhig in Schiefer und Grau */
const OHNE_GATTUNG: Gestalt = { muster: "typo", farben: [["#2f353b", "#9aa4ad", "#f1efe8"]] };

/** Die Gestalt eines Eintrags; eine unbekannte Art gilt als Buch, eine unbekannte Gattung als keine */
export const gestaltFuer = (typ = "", gattung = ""): Gestalt => ARTEN.get(typ) ?? GATTUNGEN.get(gattung) ?? OHNE_GATTUNG;

/** Der Farbsatz eines Buchs: fest nach seiner Nummer */
export const farbsatz = (gestalt: Gestalt, id: number): Dreiklang => gestalt.farben[Math.abs(Math.trunc(id)) % gestalt.farben.length];
