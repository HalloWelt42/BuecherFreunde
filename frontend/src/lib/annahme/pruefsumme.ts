// Prüfsumme einer Datei, stückweise gelesen: auch 2 GB brauchen nur wenig Speicher
import { createSHA256 } from "hash-wasm";

const STUECK = 4 * 1024 * 1024;

export async function pruefsumme(datei: Blob, fortschritt: (anteil: number) => void, abbruch: AbortSignal): Promise<string> {
  const rechner = await createSHA256();
  rechner.init();
  for (let ab = 0; ab < datei.size; ab += STUECK) {
    abbruch.throwIfAborted();
    rechner.update(new Uint8Array(await datei.slice(ab, ab + STUECK).arrayBuffer()));
    fortschritt(Math.min(1, (ab + STUECK) / datei.size));
  }
  return rechner.digest("hex");
}
