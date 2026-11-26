<script lang="ts">
  // PIN der Verwaltung vergessen (BF-78): das Konto dieses Geräts meldet sich mit Name und Kennwort erneut an, dann fällt die
  // PIN weg und das Profil öffnet ohne sie. Andere PINs setzt die Verwaltung im Elternbereich zurück.
  import { vergissPin, type Familie, type Profil } from "../../lib/api/familie";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  let { profil, onfertig, onschliessen }: { profil: Profil; onfertig: (f: Familie) => void; onschliessen: () => void } = $props();

  let kennung = $state("");
  let passwort = $state("");
  let laeuft = $state(false);
  let fehler = $state("");

  async function sende(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    try {
      onfertig(await vergissPin(profil.id, kennung.trim(), passwort));
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
      laeuft = false;
    }
  }
</script>

<Fenster titel="PIN vergessen" breite="26rem" {onschliessen}>
  <p>Mit dem Konto dieses Geräts erneut anmelden, dann öffnet {profil.name} ohne PIN. Eine neue PIN lässt sich danach unter Mein Profil setzen.</p>
  <form id="pinvergessen" class="formular" onsubmit={sende}>
    <label class="feld">{anschluesse.jetzt.anmeldung === "kellerwolke" ? "Name oder Kürzel" : "Name"}<input class="eingabe" autocomplete="username" autocapitalize="none" spellcheck="false" data-fokus bind:value={kennung} disabled={laeuft} /></label>
    <label class="feld">Kennwort<input class="eingabe" type="password" autocomplete="current-password" bind:value={passwort} disabled={laeuft} /></label>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="pinvergessen" disabled={laeuft || !kennung.trim() || !passwort}>Anmelden</button>
    </span>
  {/snippet}
</Fenster>
