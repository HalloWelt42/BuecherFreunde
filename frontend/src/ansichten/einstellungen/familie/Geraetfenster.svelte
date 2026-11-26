<script lang="ts">
  // Dieses Gerät fest auf ein Kind stellen (BF-78): mit der eigenen PIN bestätigt; danach öffnet das Gerät nur noch dieses
  // Profil, hinaus geht es nur mit der PIN eines Elternteils. Ohne eigene PIN gibt es das nicht, sonst käme jeder hinaus.
  import type { Profil } from "../../../lib/api/familie";
  import { PIN_HOECHSTENS, pinGueltig } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { profilformular } from "../../../lib/stand/profilformular.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";

  let { kind, onschliessen }: { kind: Profil; onschliessen: () => void } = $props();

  let pin = $state("");
  let laeuft = $state(false);
  let fehler = $state("");
  let ohnePin = $derived(!ich.profil?.hat_pin);

  async function binde(e: SubmitEvent) {
    e.preventDefault();
    if (!pinGueltig(pin)) return;
    laeuft = true;
    fehler = "";
    try {
      await familie.binde(kind.id, pin);
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
      laeuft = false;
    }
  }

  function eigenePin() {
    onschliessen();
    if (ich.profil) profilformular.oeffne({ profil: ich.profil });
  }
</script>

<Fenster titel="Dieses Gerät fest auf {kind.name}" breite="28rem" {onschliessen}>
  <p>Das Gerät öffnet danach immer den Bereich von {kind.name}, gleich beim Start. Hinaus geht es nur mit der PIN eines Elternteils, dann ist das Gerät wieder frei.</p>
  {#if ohnePin}
    <p class="marke-text warn">Erst eine eigene PIN setzen, sonst könnte jeder das Gerät wieder lösen.</p>
  {:else}
    <form id="geraetbindung" class="formular" onsubmit={binde}>
      <label class="feld">Deine PIN<input class="eingabe" type="password" inputmode="numeric" autocomplete="current-password" maxlength={PIN_HOECHSTENS} data-fokus bind:value={pin} disabled={laeuft} /></label>
      {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    </form>
  {/if}
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      {#if ohnePin}
        <Knopf text="Eigene PIN setzen" symbol="lock" haupt onclick={eigenePin} />
      {:else}
        <button class="knopf haupt" type="submit" form="geraetbindung" disabled={laeuft || !pinGueltig(pin)}>Fest auf {kind.name}</button>
      {/if}
    </span>
  {/snippet}
</Fenster>
