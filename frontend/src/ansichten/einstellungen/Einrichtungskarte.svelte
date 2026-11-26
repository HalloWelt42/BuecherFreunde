<script lang="ts">
  // Den Assistenten der Ersteinrichtung wieder öffnen (BF-82): er zeigt die Schritte von "Neu beginnen" ohne Konto, merkt nur vor
  // und ändert erst, was man am Ende bestätigt. Gelöscht wird nichts.
  import { navigate } from "../../lib/router.svelte";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  async function oeffne() {
    await einrichtung.oeffne();
    navigate("/settings/einrichtung");
  }
</script>

<p class="klein">Den Assistenten der Ersteinrichtung wieder öffnen. Er ändert nur, was du darin bestätigst, und löscht nichts.</p>
<div class="reihe"><Knopf text="Assistent öffnen" symbol="wand-magic-sparkles" klein laeuft={einrichtung.arbeitet} onclick={() => void einrichtung.tu(oeffne, "Nicht geöffnet")} /></div>
