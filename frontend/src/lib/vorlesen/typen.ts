// Ein Vorleser spricht einen Text mit einer seiner Stimmen. Welche es gibt, entscheidet das Gerät und was angeschlossen ist.

export interface Stimme {
  /** Vorleser und Stimme, etwa "dienst:abc" oder "geraet:Anna" */
  id: string;
  name: string;
  gruppe: string;
}

export interface Beobachter {
  /** Es klingt (nach dem Warten auf den ersten Ton) */
  klingt: () => void;
  /** Es wird auf Ton gewartet */
  wartet: () => void;
  ende: () => void;
  fehler: (grund: string) => void;
}

export interface Vorleser {
  /** Noch im Tippen rufen, sonst bleibt der Ton am Telefon stumm. */
  entsperre(): void;
  lies(text: string, stimme: string, bei: Beobachter): void;
  halt(): void;
}
