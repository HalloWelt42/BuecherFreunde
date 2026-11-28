// Zeichnet die Seiten eines PDF in ihre Rahmen ([data-seite]): nur, was sichtbar ist oder gleich wird; was weit weg ist,
// wird wieder freigegeben. Ohne Svelte, der Leser steuert über Maß und Ansicht.
import { seiteVon, type PdfBuch } from "./dokument";
import { dateiverweise, textverweise, verweisebene, type Linkanmerkung } from "./verweise";
import { geblaettert, nachbarn, sichtbareSeiten, type Ansicht } from "./zoom";

/** So viele Seiten um die gelesene bleiben gezeichnet */
const VORRAT = 8;
const SAUM = "200px 0px";

export interface Anzeigegriffe {
  /** Die oberste sichtbare Seite hat gewechselt */
  beiSeite(nr: number): void;
  /** Eine Seite ist samt Textebene gezeichnet */
  gezeichnet(nr: number, ebene: HTMLElement): void;
  /** Ein Link der Datei zeigt auf diese Seite und wurde angeklickt (BF-125) */
  springe(nr: number): void;
}

export class PdfAnzeige {
  mass = 1;
  ansicht: Ansicht = "scroll";
  seite = 1;
  #fertig = new Set<number>();
  #laeuft = new Set<number>();
  #runde = 0;
  #beobachter: IntersectionObserver | null = null;

  constructor(private buch: PdfBuch, private flaeche: HTMLElement, private griffe: Anzeigegriffe) {}

  zerstoere(): void {
    this.#beobachter?.disconnect();
    this.#runde++;
  }

  rahmen(nr: number): HTMLElement | null {
    return this.flaeche.querySelector<HTMLElement>(`[data-seite="${nr}"]`);
  }

  /** Maß oder Ansicht haben gewechselt: alles neu, die gelesene Seite bleibt oben */
  async neu(): Promise<void> {
    this.#runde++;
    this.#beobachter?.disconnect();
    this.#fertig.clear();
    this.#laeuft.clear();
    for (const r of this.flaeche.querySelectorAll<HTMLElement>("[data-seite]")) this.#leere(r);
    if (geblaettert(this.ansicht)) {
      await this.blaettere(this.seite);
      return;
    }
    this.#platzhalter();
    this.zeige(this.seite);
    this.#beobachte();
  }

  /** Geblättert: die Seite zeigen und die Nachbarn vorab zeichnen, damit der nächste Schritt sofort steht */
  async blaettere(nr: number): Promise<void> {
    this.seite = nr;
    // Rahmen, die nicht mehr da sind, zählen nicht mehr als gezeichnet
    for (const n of [...this.#fertig]) if (!this.rahmen(n)?.querySelector("canvas")) this.#fertig.delete(n);
    this.#platzhalter();
    await Promise.all(sichtbareSeiten(this.ansicht, nr, this.buch.seiten).map((n) => this.#zeichne(n)));
    if (nr !== this.seite) return;
    for (const n of nachbarn(this.ansicht, nr, this.buch.seiten).flat()) await this.#zeichne(n);
  }

  /** Seite nach oben rollen (fortlaufend) */
  zeige(nr: number): void {
    this.seite = nr;
    this.#raeume();
    const r = this.rahmen(nr);
    if (!r || this.flaeche.clientHeight === 0) return;
    this.flaeche.scrollTop += r.getBoundingClientRect().top - this.flaeche.getBoundingClientRect().top - this.#rand();
  }

  zeichneErneut(tun: (nr: number, ebene: HTMLElement) => void): void {
    for (const r of this.flaeche.querySelectorAll<HTMLElement>("[data-seite]")) {
      const ebene = r.querySelector<HTMLElement>(".textLayer");
      if (ebene) tun(Number(r.dataset.seite), ebene);
    }
  }

  #rand(): number {
    return Number.parseFloat(getComputedStyle(this.flaeche).paddingTop) || 0;
  }

  #leere(r: HTMLElement): void {
    r.querySelector("canvas")?.remove();
    r.querySelector(".textLayer")?.remove();
    r.querySelector(".verweisebene")?.remove();
  }

  // Platzhalter im Format der ersten Seite, sofort und ohne jede Seite einzeln zu laden (bei großen Büchern dauerte das
  // Sekunden bis Minuten); weicht eine Seite ab, setzt das Zeichnen ihre echte Größe
  #platzhalter(): void {
    const b = `${this.buch.mass.breite * this.mass}px`;
    const h = `${this.buch.mass.hoehe * this.mass}px`;
    for (const r of this.flaeche.querySelectorAll<HTMLElement>("[data-seite]")) {
      if (r.querySelector("canvas")) continue;
      r.style.width = b;
      r.style.height = h;
    }
  }

  #beobachte(): void {
    this.#beobachter = new IntersectionObserver((eintraege) => {
      for (const e of eintraege) {
        if (!e.isIntersecting) continue;
        const nr = Number((e.target as HTMLElement).dataset.seite);
        for (const n of [nr, nr - 1, nr + 1]) void this.#zeichne(n);
      }
      this.#meldeOberste();
    }, { root: this.flaeche, rootMargin: SAUM });
    for (const r of this.flaeche.querySelectorAll("[data-seite]")) this.#beobachter.observe(r);
  }

  /** Beim Scrollen gerufen: die oberste wirklich sichtbare Seite, nicht die erste im Vorlade-Saum */
  gerollt(): void {
    if (!geblaettert(this.ansicht)) this.#meldeOberste();
  }

  #meldeOberste(): void {
    const f = this.flaeche.getBoundingClientRect();
    if (f.height === 0) return;
    const kante = f.top + this.#rand() + 1;
    for (const r of this.flaeche.querySelectorAll<HTMLElement>("[data-seite]")) {
      const k = r.getBoundingClientRect();
      if (k.bottom <= kante) continue;
      const nr = Number(r.dataset.seite);
      if (k.top < f.bottom && nr !== this.seite) {
        this.seite = nr;
        this.griffe.beiSeite(nr);
        this.#raeume();
      }
      return;
    }
  }

  #raeume(): void {
    for (const nr of [...this.#fertig]) {
      if (Math.abs(nr - this.seite) <= VORRAT) continue;
      const r = this.rahmen(nr);
      if (r) this.#leere(r);
      this.#fertig.delete(nr);
    }
  }

  async #zeichne(nr: number): Promise<void> {
    if (nr < 1 || nr > this.buch.seiten || this.#fertig.has(nr) || this.#laeuft.has(nr)) return;
    const runde = this.#runde;
    this.#laeuft.add(nr);
    try {
      const seite = await this.buch.doc.getPage(nr);
      if (!this.rahmen(nr) || runde !== this.#runde) return;
      const blick = seite.getViewport({ scale: this.mass });
      const dichte = Math.min(window.devicePixelRatio || 1, 3);
      const bild = document.createElement("canvas");
      bild.width = Math.floor(blick.width * dichte);
      bild.height = Math.floor(blick.height * dichte);
      bild.style.width = `${blick.width}px`;
      bild.style.height = `${blick.height}px`;
      await seite.render({ canvas: bild, canvasContext: bild.getContext("2d")!, viewport: blick, transform: [dichte, 0, 0, dichte, 0, 0] }).promise;
      // Beim Blättern kann der Rahmen inzwischen ein anderer sein: erst jetzt nehmen, was gilt
      const r = this.rahmen(nr);
      if (!r || runde !== this.#runde) return;
      this.#leere(r);
      r.style.width = `${blick.width}px`;
      r.style.height = `${blick.height}px`;
      r.append(bild);
      const ebene = await this.#textebene(seite, r, blick, nr, runde);
      await this.#verweise(seite, r, blick, ebene, runde);
      if (runde === this.#runde) this.#fertig.add(nr);
    } catch (e) {
      console.warn(`Seite ${nr} nicht gezeichnet`, e);
    } finally {
      if (runde === this.#runde) this.#laeuft.delete(nr);
    }
  }

  async #textebene(seite: Awaited<ReturnType<PdfBuch["doc"]["getPage"]>>, r: HTMLElement, blick: ReturnType<typeof seite.getViewport>, nr: number, runde: number): Promise<HTMLElement> {
    const ebene = document.createElement("div");
    ebene.className = "textLayer";
    // Die Regeln von pdf.js rechnen mit diesem Maß
    ebene.style.setProperty("--total-scale-factor", String(this.mass));
    ebene.style.width = `${blick.width}px`;
    ebene.style.height = `${blick.height}px`;
    r.append(ebene);
    await new this.buch.lib.TextLayer({ textContentSource: await seite.getTextContent(), container: ebene, viewport: blick }).render();
    if (runde === this.#runde) this.griffe.gezeichnet(nr, ebene);
    return ebene;
  }

  /** Links der Datei und Adressen im Text als Flächen zum Anklicken über der Textebene (BF-125) */
  async #verweise(seite: Awaited<ReturnType<PdfBuch["doc"]["getPage"]>>, r: HTMLElement, blick: ReturnType<typeof seite.getViewport>, ebene: HTMLElement, runde: number): Promise<void> {
    const anmerkungen = (await seite.getAnnotations({ intent: "display" }).catch(() => [])) as Linkanmerkung[];
    const datei = await dateiverweise(anmerkungen, (x) => blick.convertToViewportRectangle(x), (ziel) => seiteVon(this.buch.doc, ziel));
    if (runde !== this.#runde || !ebene.isConnected) return;
    const k = r.getBoundingClientRect();
    const alle = [...datei, ...textverweise(ebene, { left: k.left + r.clientLeft, top: k.top + r.clientTop }, datei)];
    if (alle.length) r.append(verweisebene(r.ownerDocument, alle, (nr) => this.griffe.springe(nr)));
  }
}
