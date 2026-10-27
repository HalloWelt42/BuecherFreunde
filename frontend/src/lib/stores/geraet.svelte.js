/**
 * Geräteklasse: die einzige Stelle, die entscheidet, ob die Telefonansicht gilt.
 *
 * Die Telefonansicht ist die schlanke Oberfläche zum Suchen und Lesen (Suche, Buch, Leser). Sie gilt auf jedem
 * Gerät, das man mit dem Finger bedient (Telefon hoch und quer, Tablet), unabhängig von der Breite: so bleibt sie
 * erhalten, wenn man das Telefon zum Lesen quer dreht. Am Rechner gilt sie nur im schmalen Fenster.
 */

const TELEFON_ABFRAGE = "(hover: none) and (pointer: coarse), (max-width: 700px)";

function erzeugeGeraet() {
  const abfrage = window.matchMedia(TELEFON_ABFRAGE);
  let telefon = $state(abfrage.matches);
  abfrage.addEventListener("change", (e) => {
    telefon = e.matches;
  });

  return {
    get telefon() {
      return telefon;
    },
  };
}

export const geraet = erzeugeGeraet();
