// Wie viel Ton bereitliegen muss, bevor es losgeht. Reißt er ab, wächst der Vorlauf; nach ruhigen Läufen sinkt er wieder,
// nie unter den kleinen Vorlauf, mit dem es von Anfang an flüssig läuft (BF-106).

export const MINDESTENS_S = 3;
const HOECHSTENS_S = 30;

export class Vorlauf {
  noetig = MINDESTENS_S;
  #abriss = false;

  beginnen(): void {
    this.#abriss = false;
  }

  genug(bereit: number, fertig: boolean): boolean {
    return fertig || bereit >= this.noetig;
  }

  abgerissen(): void {
    this.#abriss = true;
    this.noetig = Math.min(HOECHSTENS_S, this.noetig * 1.5 + 1);
  }

  beenden(): void {
    if (!this.#abriss) this.noetig = Math.max(MINDESTENS_S, this.noetig * 0.8);
  }
}
