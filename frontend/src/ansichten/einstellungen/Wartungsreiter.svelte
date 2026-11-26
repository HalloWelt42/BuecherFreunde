<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import Bestandsangaben from "./Bestandsangaben.svelte";
  import Dateipruefung from "./Dateipruefung.svelte";
  import Einrichtungskarte from "./Einrichtungskarte.svelte";
  import Sicherung from "./Sicherung.svelte";
  import Umzug from "./Umzug.svelte";
</script>

<div class="raster">
  <Karte titel="Sicherung" symbol="shield-halved"><Sicherung /></Karte>
  <Karte titel="Umzug" symbol="truck-ramp-box"><Umzug /></Karte>
  <Karte titel="Bestand und Suche" symbol="database"><Bestandsangaben /></Karte>
  <Karte titel="Einrichtung" symbol="wand-magic-sparkles"><Einrichtungskarte /></Karte>
  <Karte titel="Dateien prüfen" symbol="magnifying-glass-chart" breit><Dateipruefung /></Karte>
</div>
