// WAV-Ton: Dauer lesen, Stille anhängen. Die Pause nach einem Satz steckt im Ton selbst, so bleibt sie auch bei gesperrtem
// Bildschirm gleich lang, wo der Browser Uhren drosselt.

interface Kopf {
  rate: number;
  jeSekunde: number;
  block: number;
  daten: number;
  laenge: number;
}

function kopf(b: ArrayBuffer): Kopf | null {
  const v = new DataView(b);
  const kennung = (ort: number) => String.fromCharCode(v.getUint8(ort), v.getUint8(ort + 1), v.getUint8(ort + 2), v.getUint8(ort + 3));
  if (b.byteLength < 44 || kennung(0) !== "RIFF" || kennung(8) !== "WAVE") return null;
  let [rate, jeSekunde, block] = [0, 0, 0];
  for (let ort = 12; ort + 8 <= b.byteLength; ) {
    const laenge = v.getUint32(ort + 4, true);
    if (kennung(ort) === "fmt ") [rate, jeSekunde, block] = [v.getUint32(ort + 12, true), v.getUint32(ort + 16, true), v.getUint16(ort + 20, true)];
    if (kennung(ort) === "data") return { rate, jeSekunde, block, daten: ort + 8, laenge: Math.min(laenge, b.byteLength - ort - 8) };
    ort += 8 + laenge + (laenge % 2);
  }
  return null;
}

/** Ton mit angehängter Stille und seine Dauer; was kein WAV ist, bleibt, wie es ist */
export function mitPause(b: ArrayBuffer, sekunden: number): { ton: Blob; dauer: number } {
  const k = kopf(b);
  if (!k?.jeSekunde) return { ton: new Blob([b]), dauer: 0 };
  const stille = Math.round((sekunden * k.jeSekunde) / k.block) * k.block;
  const neu = new Uint8Array(k.daten + k.laenge + stille);
  neu.set(new Uint8Array(b, 0, k.daten + k.laenge));
  const v = new DataView(neu.buffer);
  v.setUint32(4, neu.byteLength - 8, true);
  v.setUint32(k.daten - 4, k.laenge + stille, true);
  return { ton: new Blob([neu], { type: "audio/wav" }), dauer: (k.laenge + stille) / k.jeSekunde };
}

/** Ein Augenblick Stille, um den Ton im Tippen freizugeben */
export function stilleAdresse(): string {
  const daten = new Uint8Array(44 + 480);
  const v = new DataView(daten.buffer);
  [..."RIFF"].forEach((z, i) => v.setUint8(i, z.charCodeAt(0)));
  [..."WAVEfmt "].forEach((z, i) => v.setUint8(8 + i, z.charCodeAt(0)));
  [..."data"].forEach((z, i) => v.setUint8(36 + i, z.charCodeAt(0)));
  v.setUint32(4, 36 + 480, true);
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, 1, true);
  v.setUint32(24, 24000, true);
  v.setUint32(28, 48000, true);
  v.setUint16(32, 2, true);
  v.setUint16(34, 16, true);
  v.setUint32(40, 480, true);
  return `data:audio/wav;base64,${btoa(String.fromCharCode(...daten))}`;
}
