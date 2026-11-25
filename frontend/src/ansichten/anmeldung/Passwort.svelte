<script lang="ts">
  import { meldeAn } from "../../lib/api/anmeldung";
  import type { AppAngaben } from "../../lib/api/config";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let { angaben, onerfolg, onkoppeln }: { angaben: AppAngaben; onerfolg: (token: string) => void; onkoppeln: () => void } = $props();

  let kennung = $state("");
  let passwort = $state("");
  let fehler = $state("");
  let laeuft = $state(false);

  async function anmelden(e: SubmitEvent) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      onerfolg(await meldeAn(kennung.trim(), passwort));
    } catch (grund) {
      fehler = grund instanceof Error ? grund.message : String(grund);
    } finally {
      laeuft = false;
    }
  }
</script>

<form class="formular" onsubmit={anmelden}>
  <p class="klein">Anmelden mit deinem Konto der Kellerwolke{#if angaben.kellerwolke}{" "}unter <b>{angaben.kellerwolke}</b>{/if}.{#if angaben.besitzer}{" "}Diese App gehört dem Konto <b>{angaben.besitzer}</b>.{/if}</p>
  <label class="feld">Name oder Kürzel<input class="eingabe" autocomplete="username" autocapitalize="none" spellcheck="false" bind:value={kennung} disabled={laeuft} /></label>
  <label class="feld">Passwort<input class="eingabe" type="password" autocomplete="current-password" bind:value={passwort} disabled={laeuft} /></label>
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  <Knopf text="Anmelden" symbol="right-to-bracket" art="submit" haupt laeuft={laeuft} gesperrt={!kennung.trim() || !passwort} />
  <Knopf text="Mit Code koppeln" symbol="link" gesperrt={laeuft} onclick={onkoppeln} />
  <p class="leise">Den Code zeigt die Kellerwolke unter Einstellungen, Geräte.</p>
</form>
