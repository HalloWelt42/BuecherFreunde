<script lang="ts">
  // Zeichen eines Bereichs oder einer Kategorie im Katalog (BF-69): das helle Symbol auf der abgedunkelten Farbe seines
  // Bereichs; wie weit dunkler, rechnet lib/farbton (zeichenflaeche) für jede Farbe, auch für selbst gewählte
  import { ZEICHENFARBE, zeichenflaeche } from "../farbton";
  import { GRAUTON } from "../katalog";
  import Symbol from "./Symbol.svelte";

  let { name, farbe = GRAUTON, groesse = "" }: { name: string; farbe?: string; groesse?: "" | "klein" | "gross" } = $props();
  let flaeche = $derived(zeichenflaeche(farbe || GRAUTON));
</script>

<span class="katalogzeichen {groesse}" style:--zf={flaeche} style:--zz={ZEICHENFARBE}><Symbol name={name || "tag"} /></span>
