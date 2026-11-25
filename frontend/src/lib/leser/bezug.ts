// Worauf sich eine Frage an den Assistenten bezieht: das Buch, die Seite und der gewählte Text
import type { Bezug } from "../stand/gespraech.svelte";
import type { Lesesitzung } from "./sitzung.svelte";

export function bezugAus(sitzung: Lesesitzung, text = ""): Bezug {
  const seite = /^page:(\d+)/.exec(sitzung.griffe?.hier().cfi ?? "")?.[1];
  return { buch: sitzung.buch.id, titel: sitzung.buch.title, seite: seite ? Number(seite) : undefined, text: text.trim() || undefined };
}
