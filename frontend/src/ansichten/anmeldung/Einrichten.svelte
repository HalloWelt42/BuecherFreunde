<script lang="ts">
  // Erster Start ohne Kellerwolke: das eigene Konto anlegen
  import { richteEin } from "../../lib/api/anmeldung";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let { onerfolg }: { onerfolg: (token: string) => void } = $props();

  const MINDESTENS = 8;
  let name = $state("");
  let kennwort = $state("");
  let nochmal = $state("");
  let fehler = $state("");
  let laeuft = $state(false);
  let ungleich = $derived(nochmal !== "" && nochmal !== kennwort);

  async function anlegen(e: SubmitEvent) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      onerfolg(await richteEin(name.trim(), kennwort));
    } catch (grund) {
      fehler = grund instanceof Error ? grund.message : String(grund);
    } finally {
      laeuft = false;
    }
  }
</script>

<form class="formular" onsubmit={anlegen}>
  <p class="klein">Willkommen. Lege dein Konto an, danach geht es los.</p>
  <label class="feld">Name<input class="eingabe" autocomplete="username" autocapitalize="none" spellcheck="false" bind:value={name} disabled={laeuft} /></label>
  <label class="feld">Kennwort, mindestens {MINDESTENS} Zeichen<input class="eingabe" type="password" autocomplete="new-password" bind:value={kennwort} disabled={laeuft} /></label>
  <label class="feld">Kennwort wiederholen<input class="eingabe" type="password" autocomplete="new-password" bind:value={nochmal} disabled={laeuft} /></label>
  {#if ungleich}<p class="marke-text warn">Die Kennwörter sind verschieden.</p>{/if}
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  <Knopf text="Konto anlegen" symbol="user-plus" art="submit" haupt laeuft={laeuft} gesperrt={!name.trim() || kennwort.length < MINDESTENS || kennwort !== nochmal} />
</form>
