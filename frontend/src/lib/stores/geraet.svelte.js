/**
 * Geräteklasse: die einzige Stelle, die entscheidet, ob die Telefonansicht gilt.
 *
 * Am Telefon zeigt die App eine eigene, schlanke Oberfläche (Suche, Buch, Leser); die Ansicht am Rechner bleibt davon
 * unberührt. Maßgeblich ist allein die Breite des Fensters, damit ein schmales Fenster am Rechner dasselbe zeigt wie
 * das Telefon.
 */

const TELEFON_ABFRAGE = "(max-width: 700px)";

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
