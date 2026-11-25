// Sperrbildschirm und Kopfhörertasten: was gerade klingt und was die Tasten bewirken

export interface Werk {
  titel: string;
  autor: string;
  bild: string;
}

export interface Medientasten {
  weiter(): void;
  pause(): void;
  halt(): void;
  satzZurueck(): void;
  satzVor(): void;
  einheitZurueck(): void;
  einheitVor(): void;
}

const da = () => typeof navigator !== "undefined" && "mediaSession" in navigator;

export function zeigeMedien(werk: Werk, stueck: string, tasten: Medientasten): void {
  if (!da()) return;
  const s = navigator.mediaSession;
  s.metadata = new MediaMetadata({ title: stueck, artist: werk.autor, album: werk.titel, artwork: werk.bild ? [{ src: new URL(werk.bild, location.href).href }] : [] });
  const belege: [MediaSessionAction, () => void][] = [
    ["play", tasten.weiter], ["pause", tasten.pause], ["stop", tasten.halt], ["seekbackward", tasten.satzZurueck], ["seekforward", tasten.satzVor], ["previoustrack", tasten.einheitZurueck], ["nexttrack", tasten.einheitVor],
  ];
  for (const [aktion, tun] of belege) {
    try {
      s.setActionHandler(aktion, tun);
    } catch {
      // kennt dieser Browser nicht
    }
  }
}

export function medienStand(spielt: boolean): void {
  if (da()) navigator.mediaSession.playbackState = spielt ? "playing" : "paused";
}

export function medienAus(): void {
  if (!da()) return;
  navigator.mediaSession.metadata = null;
  navigator.mediaSession.playbackState = "none";
}
