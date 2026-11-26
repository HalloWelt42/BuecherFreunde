// Das aktive Profil (BF-78): wer liest, was es darf, Lesezeit und Katze. Die einzige Stelle, an der die Oberfläche fragt,
// ob eine Taste erscheint; der Server prüft jeden Weg ohnehin selbst.
import { ladeIch, setzeKatzenname, type Faehigkeit, type Ich, type Lesezeitstand, type Profil } from "../api/familie";

class Ichstand {
  jetzt = $state<Ich | null>(null);

  profil = $derived<Profil | null>(this.jetzt?.profil ?? null);
  #faehigkeiten = $derived(new Set<Faehigkeit>(this.jetzt?.faehigkeiten ?? []));
  istKind = $derived(this.jetzt?.profil.rolle === "kind");
  /** Erwachsene können Bücher für sich behalten */
  erwachsen = $derived(!!this.jetzt && this.jetzt.profil.rolle !== "kind");
  /** Einstellungen erscheinen, wenn mindestens ein Reiter darin erlaubt ist */
  mitEinstellungen = $derived(this.darf("einstellungen") || this.darfFamilie());

  darf(f: Faehigkeit): boolean {
    return this.#faehigkeiten.has(f);
  }

  /** Den Reiter Familie sieht, wer Profile verwaltet oder für Kinder freigibt */
  darfFamilie(): boolean {
    return this.darf("profile") || this.darf("freigeben");
  }

  istSelbst(p: Pick<Profil, "id">): boolean {
    return this.profil?.id === p.id;
  }

  /** Name, Bild und Einstellungen: das eigene Profil, mit Verwaltung alle, als Elternteil die Kinder */
  darfAendern(p: Pick<Profil, "id" | "rolle">): boolean {
    return this.istSelbst(p) || this.darf("profile") || (p.rolle === "kind" && this.darf("freigeben"));
  }

  /** Die Rolle ändert nur die Verwaltung, und nie die eigene */
  darfRolle(p: Pick<Profil, "id">): boolean {
    return this.darf("profile") && !this.istSelbst(p);
  }

  /** Löschen nur mit Verwaltung und nie das Profil, in dem man gerade liest */
  darfLoeschen(p: Pick<Profil, "id">): boolean {
    return this.darf("profile") && !this.istSelbst(p);
  }

  /** PIN setzen und entfernen: die eigene; fremde Erwachsene setzt nur die Verwaltung zurück */
  darfPin(p: Pick<Profil, "id" | "rolle">): boolean {
    return this.istSelbst(p) || this.darf("profile") || (p.rolle === "kind" && this.darf("freigeben"));
  }

  darfFreigeben(p: Pick<Profil, "rolle">): boolean {
    return p.rolle === "kind" && (this.darf("freigeben") || this.darf("profile"));
  }

  setze(ich: Ich | null): void {
    this.jetzt = ich;
  }

  async laden(): Promise<void> {
    this.jetzt = await ladeIch();
  }

  /** Das eigene Profil hat sich geändert (Name, Bild, PIN) */
  profilGeaendert(p: Profil): void {
    if (this.jetzt && this.istSelbst(p)) this.jetzt = { ...this.jetzt, profil: { ...this.jetzt.profil, ...p } };
  }

  /** Das Kind gibt seiner Katze einen Namen */
  async katzenname(name: string): Promise<void> {
    const katze = await setzeKatzenname(name);
    if (this.jetzt) this.jetzt = { ...this.jetzt, katze };
  }

  /** Neuer Stand der Lesezeit, etwa als Antwort auf das Melden aus dem Leser */
  lesezeit(stand: Lesezeitstand): void {
    if (this.jetzt) this.jetzt = { ...this.jetzt, lesezeit: stand };
  }
}

export const ich = new Ichstand();
