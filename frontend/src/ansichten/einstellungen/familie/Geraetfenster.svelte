<script lang="ts">
  // Dieses Gerät fest auf ein Kind stellen oder wieder lösen (BF-78), mit der PIN eines Elternteils. Fest gestellt öffnet das
  // Gerät nur noch dieses Profil; mit der PIN der Eltern ist die Wahl dort eine Weile offen, fest bleibt es, bis es hier gelöst
  // wird. Ohne die PIN eines Erwachsenen gibt es das nicht, sonst käme jeder hinaus. Die Verwaltung löst ohne PIN (Profilansicht).
  import type { Profil } from "../../../lib/api/familie";
  import { pinGueltig } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { profilformular } from "../../../lib/stand/profilformular.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";

  let { kind, art, onschliessen }: { kind: Profil; art: "binden" | "loesen"; onschliessen: () => void } = $props();

  let pin = $state("");
  let laeuft = $state(false);
  let fehler = $state("");
  /** Hat kein Erwachsener eine PIN, ließe sich das Gerät nicht wieder lösen */
  let ohnePin = $derived(!familie.profile.some((p) => p.rolle !== "kind" && p.hat_pin));
  let titel = $derived(art === "binden" ? `Dieses Gerät fest auf ${kind.name}` : "Dieses Gerät lösen");

  async function sende(e: SubmitEvent) {
    e.preventDefault();
    if (!pinGueltig(pin, familie.zugang)) return;
    laeuft = true;
    fehler = "";
    try {
      if (art === "binden") {
        await familie.binde(kind.id, pin);
        return;
      }
      await familie.loese(pin);
      melde.gut("Gerät gelöst");
      onschliessen();
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

<Fenster {titel} breite="28rem" {onschliessen}>
  {#if art === "binden"}
    <p>Das Gerät öffnet danach beim Start immer den Bereich von {kind.name}. Mit der PIN eines Elternteils ist die Wahl dort eine Weile offen; fest bleibt das Gerät, bis es hier gelöst wird.</p>
  {:else}
    <p>Beim Start öffnet das Gerät dann nicht mehr von selbst {kind.name}, sondern zeigt alle Profile zur Wahl.</p>
  {/if}
  {#if ohnePin && art === "binden"}
    <p class="marke-text warn">Erst braucht ein Erwachsener eine PIN, sonst ließe sich das Gerät nicht wieder lösen.</p>
  {:else}
    <form id="geraetbindung" class="formular" onsubmit={sende}>
      <label class="feld">PIN eines Elternteils<input class="eingabe" type="password" inputmode="numeric" autocomplete="current-password" maxlength={familie.zugang.pin_stellen_bis} data-fokus bind:value={pin} disabled={laeuft} /></label>
      {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    </form>
  {/if}
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      {#if ohnePin && art === "binden"}
        <Knopf text="Eigene PIN setzen" symbol="lock" haupt onclick={eigenePin} />
      {:else}
        <button class="knopf haupt" type="submit" form="geraetbindung" disabled={laeuft || !pinGueltig(pin, familie.zugang)}>{art === "binden" ? `Fest auf ${kind.name}` : "Lösen"}</button>
      {/if}
    </span>
  {/snippet}
</Fenster>
