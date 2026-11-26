<script lang="ts">
  import { untrack } from "svelte";
  import { kopple } from "../../lib/api/anmeldung";
  import type { AppAngaben } from "../../lib/api/config";
  import Codefeld from "../../lib/teile/Codefeld.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { CODE_LAENGE, codeNormal, geraeteart, geraetename } from "./kopplung";

  let { angaben, anfang, onerfolg, onzurueck }: { angaben: AppAngaben; anfang: string; onerfolg: (token: string) => void; onzurueck: () => void } = $props();

  let code = $state(untrack(() => anfang));
  let geraet = $state(geraetename(navigator.userAgent, navigator.maxTouchPoints));
  let fehler = $state("");
  let laeuft = $state(false);

  async function koppeln(e: SubmitEvent) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      onerfolg(await kopple(code, geraet.trim(), geraeteart()));
    } catch (grund) {
      fehler = grund instanceof Error ? grund.message : String(grund);
    } finally {
      laeuft = false;
    }
  }
</script>

<form class="formular" onsubmit={koppeln}>
  <p class="klein">Den Code aus der Kellerwolke{#if angaben.kellerwolke}{" "}unter <b>{angaben.kellerwolke}</b>{/if} eintippen, dort Einstellungen, Geräte. Danach bleibt dieses Gerät angemeldet, bis du es trennst. Ein Passwort wird hier nicht gespeichert.</p>
  <Codefeld {code} laenge={CODE_LAENGE} name="Kopplungscode" normal={codeNormal} onwahl={(c) => (code = c)} />
  <label class="feld">Name des Geräts<input class="eingabe" maxlength="60" bind:value={geraet} /></label>
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  <Knopf text="Koppeln" symbol="link" art="submit" haupt laeuft={laeuft} gesperrt={code.length !== CODE_LAENGE || !geraet.trim()} />
  <Knopf text="Zurück zur Anmeldung" symbol="chevron-left" gesperrt={laeuft} onclick={onzurueck} />
</form>
