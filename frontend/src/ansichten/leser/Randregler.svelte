<script lang="ts">
  import { blattrand } from "../../lib/leser/blattrand.svelte";
  import Stufenregler from "./Stufenregler.svelte";
</script>

<Stufenregler name="Rand" wert={blattrand.wert} bereich={blattrand.bereich} anzeige="{blattrand.wert} px" onwahl={(w) => (blattrand.wert = w)} />
