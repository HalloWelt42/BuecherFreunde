<script lang="ts">
  // Werkzeuge für die Angaben (BF-112), eine ruhige Reihe in drei Gruppen: was die Quellen wissen (Angaben suchen, Lexikon),
  // was im Buch selbst steht (Buchtext, Datei, Umschlag, im Kasten auf der Buchseite auch die ISBN), die KI (nur mit KI).
  // Am Telefon über die ganze Breite, das Wort unter dem Zeichen wie in der Tafel.
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { quellen } from "../../lib/stand/quellen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { DATEI, LEXIKON } from "./angaben";
  import type { Angabenwerkzeuge } from "./werkzeuge.svelte";

  let { werkzeuge: w, mitIsbn = false }: { werkzeuge: Angabenwerkzeuge; mitIsbn?: boolean } = $props();

  let ohneQuelle = $derived(quellen.geladen && !quellen.buecher.length);
  let lexikon = $derived(quellen.buecher.some((q) => q.kennung === LEXIKON));

  $effect(() => void quellen.bereit());
</script>

<div class="werkzeugreihe" role="group" aria-label="Angaben holen">
  <Knopf text="Angaben suchen" kurz="Suchen" symbol="magnifying-glass" klein gesperrt={!quellen.buecher.length} titel={ohneQuelle ? "Keine Quelle eingeschaltet" : "In allen Verzeichnissen suchen und vergleichen"} onclick={() => w.vergleiche(w.standardquelle)} />
  <Knopf text="Lexikon" symbol="book-atlas" klein gesperrt={!lexikon} titel={lexikon ? "Im Lexikon suchen und vergleichen" : "Das Lexikon ist in den Einstellungen aus"} onclick={() => w.vergleiche(LEXIKON)} />
  <Knopf text="Buchtext" symbol="book-open" klein klasse="ab" titel="Beschreibung aus den ersten Seiten" onclick={() => w.oeffne("buchtext")} />
  <Knopf text="Datei" symbol="file-import" klein titel="Titel, Autor, Verlag, Jahr und ISBN noch einmal aus der Datei lesen" onclick={() => w.vergleiche(DATEI)} />
  <Knopf text="Umschlag" symbol="image" klein titel="Umschlag neu aus der Datei" laeuft={w.holtUmschlag} onclick={() => void w.umschlag()} />
  {#if mitIsbn}<Knopf text="ISBN im Buch" kurz="ISBN" symbol="barcode" klein titel="ISBN im Buch suchen" laeuft={w.sucht} onclick={() => void w.sucheIsbn()} />{/if}
  {#if anschluesse.jetzt.ki}<Knopf text="Kategorisieren" symbol="wand-magic-sparkles" klein klasse="ab" titel="Regale von der KI vorschlagen lassen" onclick={() => w.oeffne("ki")} />{/if}
</div>
