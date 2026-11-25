// Wischen auf einer Fläche: waagrecht blättert, senkrecht rollt wie gewohnt
export interface Wischrichtung {
  links: () => void;
  rechts: () => void;
}

const SCHWELLE = 50;

export function wischen(flaeche: HTMLElement, tun: Wischrichtung): () => void {
  let start: { x: number; y: number } | null = null;

  const beginnt = (e: TouchEvent) => {
    start = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null;
  };
  // Waagrechtes Wischen gehört hier dem Leser, nicht dem Zurück des Browsers
  const bewegt = (e: TouchEvent) => {
    if (!start || e.touches.length !== 1) return;
    const dx = e.touches[0].clientX - start.x;
    const dy = e.touches[0].clientY - start.y;
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10 && e.cancelable) e.preventDefault();
  };
  const endet = (e: TouchEvent) => {
    if (!start) return;
    const dx = e.changedTouches[0].clientX - start.x;
    const dy = e.changedTouches[0].clientY - start.y;
    start = null;
    if (Math.abs(dx) < SCHWELLE || Math.abs(dx) < Math.abs(dy)) return;
    if (dx < 0) tun.links();
    else tun.rechts();
  };

  flaeche.addEventListener("touchstart", beginnt, { passive: true });
  flaeche.addEventListener("touchmove", bewegt, { passive: false });
  flaeche.addEventListener("touchend", endet, { passive: true });
  return () => {
    flaeche.removeEventListener("touchstart", beginnt);
    flaeche.removeEventListener("touchmove", bewegt);
    flaeche.removeEventListener("touchend", endet);
  };
}
