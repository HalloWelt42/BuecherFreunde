// Zustand der Schale: welche Flächen offen sind und wie breit die App gerade ist

export type Schwebefeldname = "" | "auftraege" | "darstellung" | "konto";

export const GRENZE_VORSCHAU = 1180;
export const GRENZE_LEISTE = 900;
export const GRENZE_TELEFON = 720;

class Schale {
  /** Breite der App in Bildpunkten, von App.svelte gemessen */
  breite = $state(1440);
  leisteZu = $state(false);
  leisteOffen = $state(false);
  offen = $state<Schwebefeldname>("");
  notizOffen = $state(false);
  vollbild = $state(false);

  get mitVorschau(): boolean {
    return this.breite > GRENZE_VORSCHAU;
  }
  get telefon(): boolean {
    return this.breite <= GRENZE_TELEFON;
  }

  leisteUmschalten(): void {
    if (this.breite > GRENZE_LEISTE) this.leisteZu = !this.leisteZu;
    else this.leisteOffen = !this.leisteOffen;
  }

  umschalten(feld: Schwebefeldname): void {
    this.offen = this.offen === feld ? "" : feld;
  }

  schliesseAlles(): void {
    this.offen = "";
    this.leisteOffen = false;
  }

  /** Vollbild über die Schnittstelle des Browsers; kennt er keine (iPad), füllt der Leser das Fenster. */
  async vollbildUmschalten(): Promise<void> {
    const dok = document as Document & { webkitFullscreenElement?: Element; webkitExitFullscreen?: () => Promise<void> };
    const wurzel = document.documentElement as HTMLElement & { webkitRequestFullscreen?: () => Promise<void> };
    const im = dok.fullscreenElement ?? dok.webkitFullscreenElement;
    try {
      if (im) await (dok.exitFullscreen?.() ?? dok.webkitExitFullscreen?.());
      else if (!this.vollbild) await (wurzel.requestFullscreen?.() ?? wurzel.webkitRequestFullscreen?.());
    } catch {
      // abgelehnt: dann nur das Fenster füllen
    }
    this.vollbild = im ? false : !this.vollbild;
  }

  /** Esc im Vollbild beendet der Browser selbst; der Zustand zieht nach. */
  vollbildAbgleichen(): void {
    const dok = document as Document & { webkitFullscreenElement?: Element };
    if (!dok.fullscreenElement && !dok.webkitFullscreenElement) this.vollbild = false;
  }
}

export const schale = new Schale();
