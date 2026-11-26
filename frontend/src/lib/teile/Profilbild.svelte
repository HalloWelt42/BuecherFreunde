<script lang="ts">
  // Das Bild eines Profils (BF-78): sein Symbol hell auf seiner Farbe, rund. Die Fläche dunkelt lib/farbton so weit ab,
  // dass das Zeichen auf jeder gewählten Farbe lesbar bleibt (wie die Zeichen im Katalog).
  import type { Profil } from "../api/familie";
  import { ZEICHENFARBE, zeichenflaeche } from "../farbton";
  import { GRAUTON } from "../katalog";
  import Symbol from "./Symbol.svelte";

  let { profil, groesse = "2.25rem" }: { profil: Pick<Profil, "zeichen" | "farbe"> | null; groesse?: string } = $props();
  let flaeche = $derived(zeichenflaeche(profil?.farbe || GRAUTON));
</script>

<span class="profilbild" style:--groesse={groesse} style:background={flaeche} style:color={ZEICHENFARBE}><Symbol name={profil?.zeichen || "user"} /></span>

<style>
  .profilbild {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: var(--groesse);
    height: var(--groesse);
    border-radius: 50%;
    font-size: calc(var(--groesse) * 0.44);
    box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.14);
  }
</style>
