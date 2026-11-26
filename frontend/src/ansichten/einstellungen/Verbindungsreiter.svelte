<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import { lesestoff } from "../../lib/stand/lesestoff.svelte";
  import Dienste from "./Dienste.svelte";
  import OhneNetz from "./OhneNetz.svelte";
  import Orte from "./Orte.svelte";
  import Schluessel from "./Schluessel.svelte";
  import Verbindungsliste from "./Verbindungsliste.svelte";

  $effect(() => void lesestoff.laden());
</script>

<Karte titel="Verbindungen" symbol="plug"><Verbindungsliste /></Karte>
<Karte titel="Orte" symbol="hard-drive"><Orte /></Karte>
<!-- Nur mit Dienst im Hintergrund (gebaute App über https) -->
{#if lesestoff.stand}<Karte titel="Ohne Netz lesen" symbol="wifi"><OhneNetz /></Karte>{/if}
<Karte titel="Quellen und Dienste" symbol="book-atlas" breit><Dienste /></Karte>
<Karte titel="Schlüssel dieses Browsers" symbol="key" breit><Schluessel /></Karte>
