<script lang="ts">
  // Anmeldung mit dem Konto der Kellerwolke (Passwort oder Code vom Rechner) oder mit dem eigenen Konto der App
  import { ladeAppAngaben } from "../../lib/api/anmeldung";
  import { setToken } from "../../lib/api/client";
  import type { AppAngaben } from "../../lib/api/config";
  import { darstellung, wahlen } from "../../lib/stand/darstellung.svelte";
  import Logo from "../../lib/schale/Logo.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Einrichten from "./Einrichten.svelte";
  import Koppeln from "./Koppeln.svelte";
  import Passwort from "./Passwort.svelte";
  import { codeAusAnker } from "./kopplung";

  let { onerfolg }: { onerfolg: () => void } = $props();

  const ausLink = codeAusAnker(location.hash);
  if (ausLink) history.replaceState(null, "", location.pathname + location.search);

  let mitCode = $state(!!ausLink);
  let darstellungOffen = $state(false);
  let angaben = $state<AppAngaben>({ name: "BücherFreunde", art: "kellerwolke", kellerwolke: "", besitzer: null, eingerichtet: true });

  $effect(() => {
    ladeAppAngaben().then((a) => (angaben = a)).catch(() => {});
  });

  function erfolg(token: string) {
    setToken(token);
    onerfolg();
  }
</script>

<main class="anmeldung rollen">
  <section class="anmeldekarte glas milch" aria-label="Anmeldung">
    <header class="reihe">
      <span class="anmeldelogo"><Logo /></span>
      <h1>{mitCode ? "Gerät koppeln" : angaben.name}</h1>
      <span class="schiebt"><Knopf text="Darstellung" symbol="circle-half-stroke" nur frei aufgeklappt={darstellungOffen} onclick={() => (darstellungOffen = !darstellungOffen)} /></span>
    </header>
    {#if darstellungOffen}
      <div class="platte karte">
        <div class="feld">Licht<Segment name="Licht" werte={wahlen.thema} wert={darstellung.thema} onwahl={(w) => (darstellung.thema = w)} /></div>
        <div class="feld">Schrift<Segment name="Schriftgröße" werte={wahlen.schrift} wert={darstellung.schrift} onwahl={(w) => (darstellung.schrift = w)} /></div>
      </div>
    {/if}
    {#if angaben.art === "kellerwolke" && !angaben.eingerichtet}<p class="marke-text warn">Die App ist noch nicht mit der Kellerwolke verbunden, der App-Zugang fehlt.</p>{/if}
    {#if angaben.art === "eigen" && !angaben.eingerichtet}
      <Einrichten onerfolg={erfolg} />
    {:else if mitCode && angaben.art === "kellerwolke"}
      <Koppeln {angaben} anfang={ausLink} onerfolg={erfolg} onzurueck={() => (mitCode = false)} />
    {:else}
      <Passwort {angaben} onerfolg={erfolg} onkoppeln={() => (mitCode = true)} />
    {/if}
  </section>
</main>

<style>
  .anmeldung {
    position: relative;
    z-index: 1;
    height: 100%;
    display: grid;
    place-items: center;
    padding: 1rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .anmeldekarte {
    width: min(27rem, 100%);
    padding: 1.25rem;
    display: grid;
    gap: 0.875rem;
    grid-template-columns: minmax(0, 1fr);
  }
  header {
    flex-wrap: nowrap;
  }
  h1 {
    font-size: 1.25rem;
    hyphens: auto;
    font-weight: 600;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  @container app (max-width: 20rem) {
    h1 {
      font-size: 1.0625rem;
    }
  }
  .karte .feld {
    justify-items: start;
  }
  .anmeldelogo :global(svg) {
    display: block;
    width: 2.25rem;
    height: 2.25rem;
  }
</style>
