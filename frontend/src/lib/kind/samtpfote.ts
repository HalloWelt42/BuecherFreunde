// Die Katze samtpfote von hallowelt42 als Abhängigkeit (package.json, fester Stand). Dieser Baustein liefert ihre
// Nutzungsbedingungen als eigene Datei mit aus (Lizenz Punkt 3; verlinkt im Elterndialog) und hält ihre Herkunft im Code fest.
// Die sichtbare Nennung steht in lib/kind/Katze.svelte als eigene Zeile unter der Katze (Lizenz Punkt 2).
import "samtpfote/src/lib/widget.js";
import lizenz from "samtpfote/LIZENZ.txt?url&no-inline";
import schnurren from "samtpfote/public/audio/schnurren.mp3?url";

/*! @license samtpfote | hallowelt42 | Sichtbare Namensnennung erforderlich. Nutzungsbedingungen: LIZENZ.txt, github.com/HalloWelt42/samtpfote */
export const NENNUNG = "hallowelt42 / samtpfote";
/** Die Nutzungsbedingungen, mit der App ausgeliefert */
export const LIZENZ = lizenz;
/** Die gemeinfreie Schnurr-Aufnahme (Herkunft in HERKUNFT.txt des Pakets) */
export const SCHNURREN = schnurren;
