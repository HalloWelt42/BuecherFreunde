// Im Vollbild gehört auch das Drumherum dem Blatt: Statusleiste, Kerbe und Home-Balken tragen seine Farbe

/** Färbt ein; liefert, was den alten Zustand wiederherstellt */
export function zeigeBlattgrund(farbe: string): () => void {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  const teile = [document.documentElement, document.body];
  const vorher = { meta: meta?.content, teile: teile.map((t) => t.style.background) };
  if (meta) meta.content = farbe;
  for (const t of teile) t.style.background = farbe;
  return () => {
    if (meta && vorher.meta !== undefined) meta.content = vorher.meta;
    teile.forEach((t, n) => (t.style.background = vorher.teile[n]));
  };
}
