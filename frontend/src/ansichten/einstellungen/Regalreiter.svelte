<script lang="ts">
  import Regale from "./Regale.svelte";
  import Sammlungen from "./Sammlungen.svelte";
  import Vorschlaege from "./Vorschlaege.svelte";
</script>

<!-- Die Listen der Regale und Sammlungen nutzen den freien Platz der Seite und rollen selbst (BF-74) -->
<div class="raster fuellend">
  <Regale />
  <Sammlungen />
  <Vorschlaege />
</div>
