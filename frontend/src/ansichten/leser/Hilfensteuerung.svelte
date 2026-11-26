<script lang="ts">
  // Die Lesehilfen am Rechner ohne eigene Fläche: Tastenkürzel, Lineal mit den Pfeilen, Ruhe, Zeiger, Voreinstellung je Buch.
  // Sichtbar ist nur die Fokusschicht.
  import { schreibtGerade } from "../../lib/flucht";
  import { lesehilfen, type Fokusart } from "../../lib/leser/lesehilfen.svelte";
  import { selbstlauf } from "../../lib/leser/selbstlauf.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Fokusschicht from "./Fokusschicht.svelte";

  let { sitzung, rahmen, offen }: { sitzung: Lesesitzung; rahmen: HTMLElement; offen: boolean } = $props();

  const RUHE_MS = 2500;
  const ARTEN: Fokusart[] = ["fenster", "lineal", "absatz"];
  let linealY = $state<number | null>(null);
  let zuletzt = $state(Date.now());
  let bild = 0;

  // Ruhig wird es nur, wenn nichts offen ist und man eine Weile nichts tut
  $effect(() => {
    const darf = (lesehilfen.ruhe || schale.vollbild) && !schale.telefon && !sitzung.feld && !offen;
    void zuletzt;
    sitzung.ruhig = false;
    if (!darf) return;
    const uhr = setTimeout(() => (sitzung.ruhig = true), RUHE_MS);
    return () => clearTimeout(uhr);
  });

  function regt(e: PointerEvent) {
    if (e.pointerType !== "mouse") return;
    zuletzt = Date.now();
    cancelAnimationFrame(bild);
    const [x, y] = [e.clientX, e.clientY];
    bild = requestAnimationFrame(() => {
      sitzung.zeiger = { x, y };
      if (lesehilfen.fokus.art === "lineal" && lesehilfen.fokus.folgt) linealY = null;
    });
  }

  // Lineal mit den Pfeilen: Zeile für Zeile, am Rand geht der Text weiter. Ein festes Lineal merkt sich die neue Höhe.
  function lineal(richtung: 1 | -1) {
    const h = sitzung.hilfe;
    const blatt = h?.blatt();
    if (!h || !blatt) return;
    const f = lesehilfen.fokus;
    const r = rahmen.getBoundingClientRect();
    const setze = (y: number) => (f.folgt ? (linealY = y) : lesehilfen.setzeFokus({ linie: (y - r.top) / r.height }));
    const zeile = h.zeilenhoehe();
    const jetzt = f.folgt ? (linealY ?? sitzung.zeiger?.y ?? blatt.top + blatt.height / 3) : r.top + f.linie * r.height;
    const neu = jetzt + richtung * zeile;
    const halb = (f.zeilen * zeile) / 2;
    if (neu + halb > blatt.bottom || neu - halb < blatt.top) {
      if (h.art() === "scrollen") h.rolle(richtung * zeile);
      else if (richtung > 0 && h.blaettere()) setze(blatt.top + halb + zeile);
      return;
    }
    setze(neu);
  }

  function taste(e: KeyboardEvent): boolean {
    if (schale.telefon || schreibtGerade(e) || e.ctrlKey || e.metaKey || e.altKey || document.querySelector("dialog[open]")) return false;
    zuletzt = Date.now();
    const f = lesehilfen.fokus;
    const tun: Record<string, () => void> = {
      f: () => lesehilfen.setzeFokus({ an: !f.an }),
      F: () => lesehilfen.setzeFokus({ an: true, art: ARTEN[(ARTEN.indexOf(f.art) + 1) % (sitzung.hilfe?.mitAbsaetzen ? 3 : 2)] }),
      "[": () => lesehilfen.setzeFokus({ zeilen: Math.max(1, f.zeilen - 1) }),
      "]": () => lesehilfen.setzeFokus({ zeilen: Math.min(8, f.zeilen + 1) }),
      r: () => (lesehilfen.ruhe = !lesehilfen.ruhe),
      a: () => (selbstlauf.an ? selbstlauf.halt() : sitzung.hilfe && selbstlauf.starte(sitzung.hilfe, lesehilfen.tempo)),
      v: () => void schale.vollbildUmschalten(),
      "?": () => sitzung.schalteFeld("tasten"),
    };
    let griff = tun[e.key] ?? (e.key === "R" || e.key === "A" || e.key === "V" ? tun[e.key.toLowerCase()] : undefined);
    if (e.key === " " && selbstlauf.an) griff = () => selbstlauf.pauseOderWeiter();
    if (f.an && f.art === "lineal" && !e.shiftKey && (e.key === "ArrowDown" || e.key === "ArrowUp")) griff = () => lineal(e.key === "ArrowDown" ? 1 : -1);
    if (!griff) return false;
    e.preventDefault();
    e.stopPropagation();
    griff();
    return true;
  }

  $effect(() => {
    const fang = (e: KeyboardEvent) => void taste(e);
    addEventListener("keydown", fang, true);
    rahmen.addEventListener("pointermove", regt);
    sitzung.vortaste = taste;
    const wach = () => (zuletzt = Date.now());
    rahmen.addEventListener("wheel", wach, { passive: true });
    return () => {
      removeEventListener("keydown", fang, true);
      rahmen.removeEventListener("pointermove", regt);
      rahmen.removeEventListener("wheel", wach);
      sitzung.vortaste = null;
      selbstlauf.halt();
    };
  });

  // Die Maus im Kapitelrahmen eines EPUB kommt über die Sitzung
  $effect(() => {
    void sitzung.zeiger;
    zuletzt = Date.now();
  });

  // Hat sich dieses Buch eine Voreinstellung gemerkt, gilt sie beim Öffnen
  let angewandt = false;
  $effect(() => {
    const w = sitzung.farbwahl;
    if (!w || angewandt) return;
    angewandt = true;
    const v = lesehilfen.fuerBuch(sitzung.buch.id);
    // Am Telefon gibt es die Lesehilfen nicht, auch keine gemerkte Voreinstellung (BF-40)
    if (!v || schale.telefon) return;
    w.setze(v.fg, v.bg);
    lesehilfen.setzeHilfen(v.hilfen);
  });
</script>

{#if lesehilfen.fokus.an && sitzung.hilfe && !schale.telefon}<Fokusschicht {sitzung} {rahmen} bind:linealY />{/if}
