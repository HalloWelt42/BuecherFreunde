// Was die Leiste und die Filter über den Bestand wissen: Zahlen, Regale, Sammlungen
import { get } from "../api/client";
import { ladeKategorien } from "../api/categories";
import { ladeSammlungen } from "../api/collections";
import type { Regal, Sammlung, Zahlen } from "../typen";

const LEER: Zahlen = { buecher_gesamt: 0, favoriten: 0, leseliste: 0, gelesen: 0, ungelesen: 0, buecher_mit_isbn: 0, dokumente: 0, weiterlesen: 0, autoren: 0, mit_labels: 0, mit_highlights: 0 };

type Zuhoerer = () => void;

/** "Regal 25" vor "Regal 225": Zahlen im Namen zählen als Zahlen, Groß und Klein gleich */
export const NAMENSFOLGE = new Intl.Collator("de", { numeric: true, sensitivity: "base" });

class Bestand {
  zahlen = $state<Zahlen>(LEER);
  regale = $state<Regal[]>([]);
  sammlungen = $state<Sammlung[]>([]);
  geladen = $state(false);
  #zuhoerer = new Set<Zuhoerer>();

  /** Regale, die in der Leiste stehen */
  leistenRegale = $derived(this.regale.filter((r) => r.spezial));

  async laden(): Promise<void> {
    const [zahlen, regale, sammlungen] = await Promise.allSettled([get("/api/config/stats"), ladeKategorien(), ladeSammlungen()]);
    if (zahlen.status === "fulfilled") this.zahlen = { ...LEER, ...zahlen.value };
    if (regale.status === "fulfilled") this.regale = [...regale.value].sort((a: Regal, b: Regal) => NAMENSFOLGE.compare(a.name, b.name));
    if (sammlungen.status === "fulfilled") this.sammlungen = sammlungen.value;
    this.geladen = true;
  }

  regal(id: number | string): Regal | undefined {
    return this.regale.find((r) => String(r.id) === String(id));
  }

  sammlung(id: number | string): Sammlung | undefined {
    return this.sammlungen.find((s) => String(s.id) === String(id));
  }

  /** Meldet sich, wenn Bücher dazukamen oder sich geändert haben. Gibt das Abmelden zurück. */
  beiAenderung(tun: Zuhoerer): () => void {
    this.#zuhoerer.add(tun);
    return () => this.#zuhoerer.delete(tun);
  }

  /** Nach jeder Änderung am Bestand rufen: Zahlen und offene Listen ziehen nach. */
  geaendert(): void {
    void this.laden();
    for (const tun of [...this.#zuhoerer]) tun();
  }
}

export const bestand = new Bestand();
