<script lang="ts">
  // Reiter Katalog (BF-69): wählen, ansehen und ändern, Kategorien aus Importen, Einordnen. Die Liste der Vorschläge nutzt die
  // freie Höhe und rollt selbst (BF-74); Lauf und Tasten darüber bleiben stehen.
  import AlteKategorien from "./AlteKategorien.svelte";
  import Einordnen from "./Einordnen.svelte";
  import Katalogeinstellungen from "./Katalogeinstellungen.svelte";
  import Katalogkacheln from "./Katalogkacheln.svelte";
  import Katalogwahl from "./Katalogwahl.svelte";
  import { pflege } from "./pflege.svelte";

  $effect(() => void pflege.laden());
</script>

<div class="raster fuellend katalogreiter">
  <Katalogwahl />
  {#if pflege.fehler}<p class="marke-text schlecht" role="alert">{pflege.fehler}</p>{/if}
  {#if pflege.entwurf || pflege.hatKatalog}<Katalogkacheln />{/if}
  {#if pflege.hatKatalog}
    <AlteKategorien />
    <Einordnen />
  {/if}
  <Katalogeinstellungen />
</div>
