<script lang="ts">
  import Karte from "../../lib/teile/Karte.svelte";
  import Anweisungen from "./Anweisungen.svelte";
  import KiVerbindung from "./KiVerbindung.svelte";
  import Rechtliches from "./Rechtliches.svelte";
  import Ueber from "./Ueber.svelte";
</script>

<div class="raster">
  <Karte titel="KI" symbol="wand-magic-sparkles" id="ki"><KiVerbindung /></Karte>
  <Karte titel="Anweisungen an die KI" symbol="message"><Anweisungen /></Karte>
  <Karte titel="Rechtliches" symbol="scale-balanced" breit id="rechtliches"><Rechtliches /></Karte>
  <Karte titel="Über" symbol="circle-info" breit id="ueber"><Ueber /></Karte>
</div>
