// Auswahl mehrerer Bücher im Bearbeitungsmodus
class Auswahl {
  bearbeiten = $state(false);
  #ids = $state<ReadonlySet<number>>(new Set());

  ids = $derived([...this.#ids]);
  zahl = $derived(this.#ids.size);

  hat(id: number): boolean {
    return this.#ids.has(id);
  }

  schalte(id: number): void {
    this.setze(id, !this.hat(id));
  }

  setze(id: number, an: boolean): void {
    const neu = new Set(this.#ids);
    if (an) neu.add(id);
    else neu.delete(id);
    this.#ids = neu;
  }

  fuegeHinzu(ids: Iterable<number>): void {
    this.#ids = new Set([...this.#ids, ...ids]);
  }

  ersetze(ids: Iterable<number>): void {
    this.#ids = new Set(ids);
  }

  leere(): void {
    this.#ids = new Set();
  }

  modus(an: boolean): void {
    this.bearbeiten = an;
    this.leere();
  }
}

export const auswahl = new Auswahl();
