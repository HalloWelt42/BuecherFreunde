<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import Dienste from "./Dienste.svelte";
  import Orte from "./Orte.svelte";
  import Schluessel from "./Schluessel.svelte";
  import Verbindungsliste from "./Verbindungsliste.svelte";
</script>

<Karte titel="Verbindungen" symbol="plug"><Verbindungsliste /></Karte>
<Karte titel="Orte" symbol="hard-drive"><Orte /></Karte>
<Karte titel="Quellen und Dienste" symbol="book-atlas" breit><Dienste /></Karte>
<Karte titel="Schlüssel dieses Browsers" symbol="key" breit><Schluessel /></Karte>
