<script lang="ts">
  // Der Assistent der Ersteinrichtung (BF-82, Entwurf einrichtung-1): statt der Anmeldung in ihrer Karte, breiter. Im Kopf das
  // Zeichen, die Ausgangslage und die Darstellung (Hell, Dunkel, System, Schrift) von Anfang an.
  import Logo from "../../lib/schale/Logo.svelte";
  import { lagetitel, WILLKOMMEN } from "../../lib/einrichtung/ablauf";
  import { darstellung, wahlen } from "../../lib/stand/darstellung.svelte";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Schritte from "./Schritte.svelte";
  import Willkommen from "./Willkommen.svelte";

  let { angemeldet }: { angemeldet: boolean } = $props();

  let darstellungOffen = $state(false);
</script>

<main class="anmeldung ew-einrichtung">
  <section class="anmeldekarte glas milch ew-assistent" aria-label="Einrichtung">
    <header class="reihe">
      <span class="anmeldelogo"><Logo /></span>
      <h1>{einrichtung.zeigtWillkommen ? WILLKOMMEN : lagetitel(einrichtung.lauf)}</h1>
      <span class="schiebt"><Knopf text="Darstellung" symbol="circle-half-stroke" nur frei aufgeklappt={darstellungOffen} onclick={() => (darstellungOffen = !darstellungOffen)} /></span>
    </header>
    {#if darstellungOffen}
      <div class="platte karte ew-darstellung">
        <div class="feld">Licht<span class="ew-voll"><Segment name="Licht" werte={wahlen.thema} wert={darstellung.thema} onwahl={(w) => (darstellung.thema = w)} /></span></div>
        <div class="feld">Schrift<span class="ew-voll ew-vier"><Segment name="Schriftgröße" werte={wahlen.schrift} wert={darstellung.schrift} onwahl={(w) => (darstellung.schrift = w)} /></span></div>
      </div>
    {/if}
    {#if einrichtung.zeigtWillkommen}<Willkommen />{:else}<Schritte {angemeldet} />{/if}
  </section>
</main>
