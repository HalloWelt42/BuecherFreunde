<script lang="ts">
  import Darstellungswahl from "../../lib/schale/Darstellungswahl.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Hintergrundbilder from "./Hintergrundbilder.svelte";
</script>

<Karte titel="Darstellung" symbol="palette"><Darstellungswahl /></Karte>
<Karte titel="Eigene Hintergrundbilder" symbol="image"><Hintergrundbilder /></Karte>
