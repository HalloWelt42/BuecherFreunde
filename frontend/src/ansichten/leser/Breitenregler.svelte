<script lang="ts">
  // Breite des Blatts für alle Formate, je Gerät gemerkt (BF-36): Textspalte in Text, Markdown und EPUB, Seite im PDF
  import { blattbreite } from "../../lib/leser/leseraum.svelte";
  import Stufenregler from "./Stufenregler.svelte";
</script>

<Stufenregler name="Breite" wert={blattbreite.wert} bereich={blattbreite.bereich} sprung={40} anzeige="{blattbreite.wert} px" onwahl={(w) => (blattbreite.wert = w)} />
