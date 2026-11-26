<script lang="ts">
  // Schritt Neuaufbau: aus dem Auszug je Buch entstehen Bücher, Angaben, Volltext, Umschläge und das Persönliche je Profil;
  // jeder Teil mit eigenem Balken. Weiter geht es, wenn der Auftrag fertig ist.
  import { onDestroy } from "svelte";
  import { beginneNeuaufbau, ladeAuftraege, type Auftragsstand, type Schritt } from "../../lib/api/einrichtung";
  import { TEILZEICHEN } from "../../lib/einrichtung/ablauf";
  import { laeuftNoch } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Auftragsfeld from "./Auftragsfeld.svelte";
  import Hinweis from "./Hinweis.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let auftrag = $state<Auftragsstand | null>(null);
  let geladen = $state(false);

  const halt = imTakt(async () => {
    auftrag = (await ladeAuftraege()).find((a) => a.art === "neuaufbau") ?? null;
    geladen = true;
    if (auftrag?.stand === "fertig" && !schritt.weiter) await einrichtung.laden();
    // Vor dem Beginn fragt der Takt weiter, bis der Auftrag läuft
    return !auftrag?.stand || laeuftNoch(auftrag);
  }, 1500);
  onDestroy(halt);

  let laeuft = $derived(laeuftNoch(auftrag));
  let fertig = $derived(auftrag?.stand === "fertig");
</script>

<Schrittrahmen zurueck={laeuft ? "gesperrt" : true} weiter={{ gesperrt: !fertig, titel: fertig ? undefined : "Erst nach dem Neuaufbau" }}>
  {#if !geladen}
    <Zustand art="laedt" text="Stand des Neuaufbaus wird geholt" />
  {:else if auftrag?.stand}
    <Auftragsfeld {auftrag} wort="Büchern fertig" teile={TEILZEICHEN.neuaufbau} onneu={(a) => (auftrag = a)} />
    {#if laeuft}<Hinweis />{/if}
  {:else}
    <p class="leise">Der Neuaufbau hat noch nicht begonnen.</p>
    <div class="reihe"><Knopf text="Neu aufbauen" symbol="arrows-rotate" haupt onclick={() => void einrichtung.tu(async () => (auftrag = await beginneNeuaufbau()), "Neuaufbau nicht begonnen")} /></div>
  {/if}
</Schrittrahmen>
