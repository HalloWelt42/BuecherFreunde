<script lang="ts">
  // Es gibt jetzt ein Konto (aus der Sicherung, vom alten Gerät oder der Kellerwolke), dieses Gerät ist aber noch nicht
  // angemeldet: erst anmelden, dann geht der Assistent am selben Schritt weiter.
  import { ladeAppAngaben } from "../../lib/api/anmeldung";
  import { setToken } from "../../lib/api/client";
  import type { AppAngaben } from "../../lib/api/config";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Koppeln from "../anmeldung/Koppeln.svelte";
  import Passwort from "../anmeldung/Passwort.svelte";

  let angaben = $state<AppAngaben | null>(null);
  let mitCode = $state(false);

  $effect(() => {
    ladeAppAngaben().then((a) => (angaben = a)).catch(() => {});
  });

  const herkunft = $derived(
    einrichtung.lauf === "sicherung" ? "Konto und Profile kommen aus der Sicherung." : einrichtung.lauf === "umzug" ? "Konto und Profile kommen vom alten Gerät." : "Das Konto ist eingerichtet.",
  );

  function erfolg(token: string) {
    setToken(token);
    location.reload();
  }
</script>

<div class="ew-schritt rollen">
  <p class="marke-text gut"><Symbol name="circle-check" />{herkunft}</p>
  <p class="klein">Melde dich mit diesem Konto an, dann geht es hier weiter.</p>
  {#if angaben}
    {#if mitCode && angaben.art === "kellerwolke"}
      <Koppeln {angaben} anfang="" onerfolg={erfolg} onzurueck={() => (mitCode = false)} />
    {:else}
      <Passwort {angaben} onerfolg={erfolg} onkoppeln={() => (mitCode = true)} />
    {/if}
  {/if}
</div>
