<script lang="ts">
  import { abmelden } from "../api/client";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";

  async function ab() {
    schale.schliesseAlles();
    await abmelden();
  }
</script>

<p class="leise">Eine Anmeldung für Bücher, Hochladen und Assistent.</p>
<div class="reihe"><Knopf text="Abmelden" symbol="right-from-bracket" onclick={ab} /></div>

<style>
  p {
    padding-bottom: 0.75rem;
  }
</style>
