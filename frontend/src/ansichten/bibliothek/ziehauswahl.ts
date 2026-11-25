// Auswählen durch Ziehen mit der Maus: im Regal mit einem Rechteck, in der Liste Zeile für Zeile.
// Die Kinder tragen data-buch="ID". Mit dem Finger rollt die Fläche wie gewohnt.
import { auswahl } from "../../lib/stand/auswahl.svelte";

const SCHWELLE = 6;
const RAND = 48;

export interface Ziehoptionen {
  an: boolean;
  art: "rechteck" | "zeilen";
}

function buecherIn(wurzel: HTMLElement): HTMLElement[] {
  return [...wurzel.querySelectorAll<HTMLElement>("[data-buch]")];
}

export function ziehauswahl(wurzel: HTMLElement, optionen: Ziehoptionen) {
  let o = optionen;
  let aktiv = false;
  let x0 = 0;
  let y0 = 0;
  let rahmen: HTMLElement | null = null;
  let setzt = true;
  let unterdrueckeKlick = false;

  const rolle = () => wurzel.closest<HTMLElement>(".rollen");
  const roll = () => rolle()?.scrollTop ?? 0;
  const buchBei = (e: PointerEvent) => (document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-buch]") as HTMLElement | null) ?? null;

  function beginne(e: PointerEvent) {
    if (!o.an || e.pointerType !== "mouse" || e.button !== 0) return;
    if (o.art === "zeilen" && !buchBei(e)) return;
    x0 = e.clientX;
    y0 = e.clientY + roll();
    addEventListener("pointermove", bewege);
    addEventListener("pointerup", beende, { once: true });
    // Ein zweiter Rückzug der Textauswahl: während des Ziehens wird nichts markiert
    e.preventDefault();
  }

  function bewege(e: PointerEvent) {
    const y = e.clientY + roll();
    if (!aktiv) {
      if (Math.abs(e.clientX - x0) < SCHWELLE && Math.abs(y - y0) < SCHWELLE) return;
      aktiv = true;
      if (o.art === "zeilen") {
        const erste = document.elementFromPoint(x0, y0 - roll())?.closest<HTMLElement>("[data-buch]");
        setzt = erste ? !auswahl.hat(Number(erste.dataset.buch)) : true;
        if (erste) auswahl.setze(Number(erste.dataset.buch), setzt);
      }
    }
    if (o.art === "zeilen") {
      const zeile = buchBei(e);
      if (zeile) auswahl.setze(Number(zeile.dataset.buch), setzt);
    } else zeichne(e.clientX, y);
    rolleAmRand(e.clientY);
  }

  function zeichne(x: number, y: number) {
    const flaeche = rolle();
    if (!flaeche) return;
    const f = flaeche.getBoundingClientRect();
    if (!rahmen) {
      rahmen = document.createElement("div");
      rahmen.className = "auswahlrahmen";
      flaeche.appendChild(rahmen);
    }
    Object.assign(rahmen.style, { left: `${Math.min(x, x0) - f.left}px`, top: `${Math.min(y, y0) - f.top}px`, width: `${Math.abs(x - x0)}px`, height: `${Math.abs(y - y0)}px` });
    const r = rahmen.getBoundingClientRect();
    auswahl.fuegeHinzu(
      buecherIn(wurzel)
        .filter((b) => {
          const k = b.getBoundingClientRect();
          return k.left < r.right && k.right > r.left && k.top < r.bottom && k.bottom > r.top;
        })
        .map((b) => Number(b.dataset.buch)),
    );
  }

  function rolleAmRand(y: number) {
    const flaeche = rolle();
    if (!flaeche) return;
    const f = flaeche.getBoundingClientRect();
    if (y > f.bottom - RAND) flaeche.scrollTop += 14;
    else if (y < f.top + RAND) flaeche.scrollTop -= 14;
  }

  function beende() {
    removeEventListener("pointermove", bewege);
    rahmen?.remove();
    rahmen = null;
    unterdrueckeKlick = aktiv;
    aktiv = false;
  }

  // Nach dem Ziehen folgt noch ein Klick: der soll die letzte Kachel nicht wieder umschalten
  function klick(e: MouseEvent) {
    if (!unterdrueckeKlick) return;
    unterdrueckeKlick = false;
    e.preventDefault();
    e.stopPropagation();
  }

  wurzel.addEventListener("pointerdown", beginne);
  wurzel.addEventListener("click", klick, true);
  return {
    update(neu: Ziehoptionen) {
      o = neu;
    },
    destroy() {
      wurzel.removeEventListener("pointerdown", beginne);
      wurzel.removeEventListener("click", klick, true);
      removeEventListener("pointermove", bewege);
    },
  };
}
