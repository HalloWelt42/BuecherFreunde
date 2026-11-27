<script lang="ts">
  // Solange "Bei Gutendex suchen" wartet (BF-98): seit wann, Abbrechen und warum es dauern darf; die Vorschläge darunter lassen
  // sich schon wählen und holen
  import { dauer } from "../../../lib/format";
  import { gutenberg as g, wartehinweis } from "../../../lib/stand/gutenberg.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
</script>

<section class="mulde auftrag gutendex-wartet" aria-live="polite">
  <div class="reihe"><b>Gutendex wird gefragt</b><span class="leise zahl">seit {dauer(g.sekunden)}</span><span class="schiebt"><Knopf text="Abbrechen" symbol="xmark" klein frei onclick={() => g.abbrechen()} /></span></div>
  <Balken unbestimmt name="Gutendex wird gefragt" />
  <span class="leise">{wartehinweis(g.katalog?.suche_geduld_s, g.treffer.length > 0)}</span>
</section>
