<!-- Wer liest: Bild und Name des Kindes, oder an seiner Stelle ein Titel -->
<script lang="ts">
  import type { Kinderprofil } from "../../lib/kind/typen";

  let { profil, titel = "" }: { profil: Kinderprofil; titel?: string } = $props();
</script>

<span class="k-wer">
  <span class="k-bild" style:background={profil.farbe} aria-hidden="true"><i class="fa-solid fa-{profil.zeichen}"></i></span>
  <span>{titel || profil.name}</span>
</span>
