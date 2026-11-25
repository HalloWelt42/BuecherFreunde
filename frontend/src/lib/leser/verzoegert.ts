// Speichern beim Tippen: je Feld erst nach kurzer Ruhe, beim Verlassen sofort
const RUHE_MS = 800;

export class Verzoegert {
  #offen = new Map<string, { uhr: ReturnType<typeof setTimeout>; tun: () => unknown }>();

  rufe(schluessel: string, tun: () => unknown): void {
    clearTimeout(this.#offen.get(schluessel)?.uhr);
    this.#offen.set(schluessel, { tun, uhr: setTimeout(() => this.#jetzt(schluessel), RUHE_MS) });
  }

  #jetzt(schluessel: string): void {
    const eintrag = this.#offen.get(schluessel);
    if (!eintrag) return;
    clearTimeout(eintrag.uhr);
    this.#offen.delete(schluessel);
    eintrag.tun();
  }

  alle(): void {
    for (const schluessel of [...this.#offen.keys()]) this.#jetzt(schluessel);
  }
}
