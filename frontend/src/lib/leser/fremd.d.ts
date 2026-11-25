// Bibliothek ohne eigene Typen: nur, was der Leser davon benutzt
declare module "foliate-js/view.js" {
  export interface FoliateKapitel {
    label: string;
    href: string;
    subitems?: FoliateKapitel[];
  }
  export interface FoliateInhalt {
    index: number;
    doc: Document;
  }
  export interface FoliateStand {
    fraction?: number;
    cfi?: string;
    tocItem?: FoliateKapitel;
    pageItem?: FoliateKapitel;
  }
  export interface FoliateAnmerkung {
    value: string;
    color?: string;
  }
  export class View extends HTMLElement {
    book?: { toc?: FoliateKapitel[]; metadata?: { language?: string | string[] }; sections: unknown[] };
    renderer?: HTMLElement & {
      getContents(): FoliateInhalt[];
      setStyles?(css: string): void;
      /** Im Umbruch der Bibliothek; Bücher mit festen Seiten haben das nicht */
      readonly scrolled?: boolean;
      readonly start?: number;
      readonly end?: number;
      readonly viewSize?: number;
      readonly atEnd?: boolean;
    };
    open(datei: File): Promise<void>;
    close(): void;
    init(o: { lastLocation?: string }): Promise<void>;
    goTo(ziel: string | number): Promise<unknown>;
    goToFraction(anteil: number): Promise<void>;
    next(weite?: number): Promise<void>;
    prev(weite?: number): Promise<void>;
    getCFI(index: number, bereich?: Range): string;
    resolveCFI(cfi: string): { index: number; anchor?: (doc: Document) => Range };
    getSectionFractions(): number[];
    addAnnotation(a: FoliateAnmerkung, weg?: boolean): Promise<unknown>;
    deleteAnnotation(a: FoliateAnmerkung): Promise<unknown>;
    search(o: { query: string }): AsyncGenerator<string | { subitems?: { cfi: string }[]; cfi?: string; progress?: number }>;
    clearSearch(): void;
  }
}

declare module "foliate-js/overlayer.js" {
  export const Overlayer: { highlight: unknown };
}
