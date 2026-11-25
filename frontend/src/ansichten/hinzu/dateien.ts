// Dateien aus einem Ziehvorgang, auch aus ganzen Ordnern
const VERSTECKT = /^(\.|Thumbs\.db$|desktop\.ini$)/i;

export function brauchbar(dateien: Iterable<File>): File[] {
  return [...dateien].filter((d) => !VERSTECKT.test(d.name));
}

async function eintraege(ordner: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
  const leser = ordner.createReader();
  const alle: FileSystemEntry[] = [];
  // Der Browser liefert höchstens hundert auf einmal; leer heißt fertig
  for (;;) {
    const teil = await new Promise<FileSystemEntry[]>((r, f) => leser.readEntries(r, f));
    if (!teil.length) return alle;
    alle.push(...teil);
  }
}

async function dateienAus(eintrag: FileSystemEntry): Promise<File[]> {
  if (eintrag.isFile) return [await new Promise<File>((r, f) => (eintrag as FileSystemFileEntry).file(r, f))];
  const teile = await Promise.all((await eintraege(eintrag as FileSystemDirectoryEntry)).map(dateienAus));
  return teile.flat();
}

export async function gezogeneDateien(ziehen: DataTransfer): Promise<File[]> {
  const wurzeln = [...ziehen.items].map((i) => i.webkitGetAsEntry?.()).filter((e): e is FileSystemEntry => !!e);
  // Die Liste gilt nur während des Ereignisses: vor dem ersten Warten abholen
  const einzeln = [...ziehen.files];
  if (!wurzeln.some((e) => e.isDirectory)) return brauchbar(einzeln);
  return brauchbar((await Promise.all(wurzeln.map(dateienAus))).flat());
}
