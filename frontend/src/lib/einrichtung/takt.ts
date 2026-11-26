// Regelmäßig nachfragen, solange ein Auftrag läuft (BF-82): gleich einmal, dann im Takt, bis `tun` false liefert oder die
// zurückgegebene Funktion den Takt beendet. Ein Fehler hält den Takt nicht an, die nächste Runde fragt wieder.
export function imTakt(tun: () => Promise<boolean | void>, ms: number): () => void {
  let aus = false;
  let uhr: ReturnType<typeof setTimeout> | undefined;
  const runde = async () => {
    let weiter = true;
    try {
      weiter = (await tun()) !== false;
    } catch {
      // die nächste Runde fragt wieder
    }
    if (!aus && weiter) uhr = setTimeout(runde, ms);
  };
  void runde();
  return () => {
    aus = true;
    clearTimeout(uhr);
  };
}
