// Bibliotheken ohne eigene Typen: nur, was der Kinderbereich davon benutzt

declare module "hyphen/de-1996" {
  interface Trennwahl {
    hyphenChar?: string;
    minWordLength?: number;
  }
  export function hyphenateSync(text: string, wahl?: Trennwahl): string;
}

// samtpfote von hallowelt42 (github.com/HalloWelt42/samtpfote): das Element <samt-pfote>, eingebunden in lib/kind/Katze.svelte
declare module "samtpfote/src/lib/widget.js" {
  export class Samtpfote extends HTMLElement {
    perform(aktion: "curious" | "sleeping" | "drowsy" | "stretching" | "grooming" | "petting" | "swatting" | "auto"): void;
    configure(wahl: Record<string, unknown>): this;
    readonly state: string;
  }
}

declare module "samtpfote/public/audio/schnurren.mp3?url" {
  const adresse: string;
  export default adresse;
}

// Ergänzt die Angaben in lib/leser/fremd.d.ts: ein Buch öffnen, ohne es anzuzeigen
declare module "foliate-js/view.js" {
  export interface FoliateAbschnitt {
    linear?: string;
    cfi?: string;
    load(): Promise<string | null>;
    unload?(): void;
    createDocument(): Promise<Document>;
    resolveHref?(href: string): string;
  }
  export interface FoliateBuch {
    sections: FoliateAbschnitt[];
    metadata?: { title?: unknown; language?: string | string[] };
    resolveCFI?(cfi: string): { index: number; anchor?: (doc: Document) => Range | Element | number };
    destroy?(): void;
  }
  export function makeBook(datei: File): Promise<FoliateBuch>;
}

declare module "foliate-js/epubcfi.js" {
  export function fromRange(bereich: Range): string;
  export function joinIndir(...teile: string[]): string;
  export function parse(cfi: string): unknown;
  export const fake: { fromIndex(index: number): string; toIndex(teile: unknown): number };
}
