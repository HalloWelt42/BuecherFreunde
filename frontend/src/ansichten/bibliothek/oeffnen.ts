// Ein Klick wählt das Buch für die Vorschau, der zweite öffnet die Buchseite; ohne Vorschau öffnet schon der erste.
// Mit Cmd, Strg, Umschalt, Alt oder mittlerer Taste gilt der Browser (neuer Tab).
import { navigate } from "../../lib/router.svelte";
import { auswahl } from "../../lib/stand/auswahl.svelte";
import { schale } from "../../lib/stand/schale.svelte";
import { wahl } from "../../lib/stand/wahl.svelte";
import type { Buch } from "../../lib/typen";

export function beimKlick(e: MouseEvent, buch: Buch): void {
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  if (auswahl.bearbeiten) return;
  if (schale.mitVorschau && wahl.buch?.id !== buch.id) wahl.waehle(buch);
  else {
    wahl.waehle(buch);
    navigate(`/book/${buch.id}`);
  }
}
