<script lang="ts">
  // Willkommen: die vier Ausgangslagen als gleich große Kacheln; ein Tipp wählt und beginnt
  import { LAGEN } from "../../lib/einrichtung/ablauf";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Kachel from "./Kachel.svelte";
</script>

<div class="ew-schritt rollen">
  <p class="klein">Neue Installation. Womit beginnst du?</p>
  <div class="ew-kacheln">
    {#each LAGEN as [lage, bild] (lage)}
      <Kachel symbol={bild.symbol} farbe={bild.farbe} titel={bild.titel} text={bild.text} gesperrt={einrichtung.arbeitet}
        onclick={() => void einrichtung.tu(() => einrichtung.waehle(lage), "Nicht gewählt")} />
    {/each}
  </div>
</div>
