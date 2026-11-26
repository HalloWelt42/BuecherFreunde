<script lang="ts">
  // Schritt Konto: ein eigenes Konto anlegen oder die Kellerwolke mit ihrem App-Zugang eintragen und sich dann mit dem Konto
  // dort anmelden. Das Konto meldet dieses Gerät an und wird das erste Profil Verwaltung. Danach beginnt die Seite neu, mit
  // Anmeldung, und der Assistent steht am nächsten Schritt.
  import { richteEin } from "../../lib/api/anmeldung";
  import { setToken } from "../../lib/api/client";
  import { kontoMitKellerwolke, type Schritt } from "../../lib/api/einrichtung";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { ich } from "../../lib/stand/ich.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  const MINDESTENS = 8;
  const WEGE: ["eigen" | "wolke", string][] = [["eigen", "Eigenes Konto"], ["wolke", "Konto der Kellerwolke"]];
  let weg = $state<"eigen" | "wolke">("eigen");
  let name = $state("");
  let kennwort = $state("");
  let nochmal = $state("");
  let adresse = $state("");
  let zugang = $state("");
  let fehler = $state("");

  let ungleich = $derived(nochmal !== "" && nochmal !== kennwort);
  let grund = $derived(
    weg === "wolke"
      ? !adresse.trim() ? "Erst die Adresse der Kellerwolke" : zugang.trim().length < MINDESTENS ? "Erst den App-Zugang der Kellerwolke" : ""
      : !name.trim() ? "Erst einen Namen" : kennwort.length < MINDESTENS ? `Das Kennwort braucht mindestens ${MINDESTENS} Zeichen` : kennwort !== nochmal ? "Die Kennwörter sind verschieden" : "",
  );

  async function anlegen() {
    fehler = "";
    try {
      if (weg === "eigen") {
        setToken(await richteEin(name.trim(), kennwort));
        location.reload();
        return;
      }
      await kontoMitKellerwolke(adresse.trim(), zugang.trim());
      // Jetzt gibt es ein Konto: der Assistent fragt nach der Anmeldung mit dem Konto der Kellerwolke
      await einrichtung.laden();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  function absenden(e: SubmitEvent) {
    e.preventDefault();
    if (!grund) void einrichtung.tu(anlegen);
  }
</script>

<Schrittrahmen weiter={schritt.stand === "erledigt" ? {} : { gesperrt: !!grund, titel: grund || undefined, tun: anlegen }}>
  {#if schritt.stand === "erledigt"}
    <p class="marke-text gut"><Symbol name="circle-check" />{schritt.text}</p>
    {#if ich.profil}<p class="leise">Angemeldet als {ich.profil.name}.</p>{/if}
  {:else}
    <form id="kontoformular" class="formular" onsubmit={absenden}>
      <div class="feld">Anmeldung<span class="ew-voll"><Segment name="Anmeldung" werte={WEGE} wert={weg} onwahl={(w) => (weg = w)} /></span></div>
      {#if weg === "eigen"}
        <label class="feld">Name<input class="eingabe" autocomplete="username" autocapitalize="none" spellcheck="false" bind:value={name} /></label>
        <label class="feld">Kennwort, mindestens {MINDESTENS} Zeichen<input class="eingabe" type="password" autocomplete="new-password" bind:value={kennwort} /></label>
        <label class="feld">Kennwort wiederholen<input class="eingabe" type="password" autocomplete="new-password" bind:value={nochmal} /></label>
        {#if ungleich}<p class="marke-text warn">Die Kennwörter sind verschieden.</p>{/if}
        <p class="leise ew-hinweiszeile"><Symbol name="user-shield" /><span>Das Konto meldet dieses Gerät an und wird das erste Profil, mit der Rolle Verwaltung.</span></p>
      {:else}
        <label class="feld">Adresse der Kellerwolke<input class="eingabe" type="url" placeholder="https://wolke.beispiel.lan" autocomplete="off" spellcheck="false" bind:value={adresse} /></label>
        <label class="feld">App-Zugang der Kellerwolke<input class="eingabe" type="password" autocomplete="off" spellcheck="false" bind:value={zugang} /></label>
        <p class="leise ew-hinweiszeile"><Symbol name="user-shield" /><span>Der Server prüft den Zugang und legt ihn in seiner Schlüsseldatei ab. Danach meldest du dich mit deinem Konto der Kellerwolke an; es wird das erste Profil, mit der Rolle Verwaltung.</span></p>
      {/if}
      {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
      <button type="submit" hidden aria-hidden="true" tabindex="-1"></button>
    </form>
  {/if}
</Schrittrahmen>
