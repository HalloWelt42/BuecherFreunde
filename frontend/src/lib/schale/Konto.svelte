<script lang="ts">
  import { aendereKennwort } from "../api/anmeldung";
  import { abmelden } from "../api/client";
  import { anschluesse } from "../stand/anschluesse.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";

  let eigen = $derived(anschluesse.jetzt.anmeldung === "eigen");
  let offen = $state(false);
  let alt = $state("");
  let neu = $state("");
  let laeuft = $state(false);

  async function ab() {
    schale.schliesseAlles();
    await abmelden();
  }

  async function aendere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    try {
      await aendereKennwort(alt, neu);
      melde.gut("Kennwort geändert. Bitte neu anmelden.");
      await ab();
    } catch (grund) {
      melde.schlecht(grund);
    } finally {
      laeuft = false;
    }
  }
</script>

<p class="leise">Eine Anmeldung für Bücher, Hochladen{anschluesse.jetzt.assistent ? " und Assistent" : " und Einstellungen"}.</p>
{#if eigen && offen}
  <form class="formular" onsubmit={aendere}>
    <label class="feld">Bisheriges Kennwort<input class="eingabe" type="password" autocomplete="current-password" bind:value={alt} disabled={laeuft} /></label>
    <label class="feld">Neues Kennwort, mindestens 8 Zeichen<input class="eingabe" type="password" autocomplete="new-password" bind:value={neu} disabled={laeuft} /></label>
    <Knopf text="Kennwort ändern" symbol="check" art="submit" haupt {laeuft} gesperrt={!alt || neu.length < 8} />
  </form>
{/if}
<div class="reihe">
  <Knopf text="Abmelden" symbol="right-from-bracket" onclick={ab} />
  {#if eigen && !offen}<Knopf text="Kennwort ändern" symbol="key" onclick={() => (offen = true)} />{/if}
</div>

<style>
  p,
  form {
    padding-bottom: 0.75rem;
  }
</style>
