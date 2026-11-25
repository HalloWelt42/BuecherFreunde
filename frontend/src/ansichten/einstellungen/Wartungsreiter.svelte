<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import Bestandsangaben from "./Bestandsangaben.svelte";
  import Dateipruefung from "./Dateipruefung.svelte";
  import Sicherung from "./Sicherung.svelte";
</script>

<Karte titel="Sicherung" symbol="shield-halved"><Sicherung /></Karte>
<Karte titel="Bestand und Suche" symbol="database"><Bestandsangaben /></Karte>
<Karte titel="Dateien prüfen" symbol="magnifying-glass-chart" breit><Dateipruefung /></Karte>
