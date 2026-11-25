<script lang="ts">
  // Die Tastenkürzel des Lesers auf einen Blick
  const KUERZEL: [string, string][] = [
    ["F", "Fokus an oder aus"], ["Umschalt F", "Art des Fokus wechseln"], ["[ und ]", "Lineal niedriger, höher"], ["Pfeil hoch, runter", "Lineal eine Zeile, wenn es an ist"],
    ["R", "Ruhe an oder aus"], ["A", "Von selbst lesen"], ["Leertaste", "Von selbst lesen anhalten, sonst blättern"], ["V", "Vollbild"],
    ["+ und -", "Schrift größer, kleiner"], ["Pfeil links, rechts", "Seite zurück, weiter"], ["Pos1, Ende", "Anfang, Ende"], ["?", "Diese Übersicht"], ["Esc", "Feld schließen, Vollbild verlassen"],
  ];
</script>

<h2>Tastenkürzel</h2>
<table class="tabelle kuerzel">
  <tbody>
    {#each KUERZEL as [taste, wirkung] (taste)}<tr><td><kbd>{taste}</kbd></td><td>{wirkung}</td></tr>{/each}
  </tbody>
</table>

<style>
  .kuerzel td:first-child {
    white-space: nowrap;
    width: 1%;
  }
  kbd {
    display: inline-block;
    padding: 0.0625rem 0.375rem;
    border-radius: var(--r1);
    background: var(--vertieft);
    box-shadow: inset 0 0 0 1px var(--linie);
    font: 500 0.8125rem var(--schrift);
  }
</style>
