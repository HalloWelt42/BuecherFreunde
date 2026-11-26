<script lang="ts">
  // Schritt Prüfung der Originale: die App sucht jedes Original, fehlende über die Prüfsumme in der Kellerwolke. Weiter geht es
  // erst, wenn der Auftrag fertig ist; Pause hält ihn an.
  import { onDestroy } from "svelte";
  import { beginnePruefung, ladeAuftraege, type Auftragsstand, type Schritt } from "../../lib/api/einrichtung";
  import { laeuftNoch, teilwert } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Auftragsfeld from "./Auftragsfeld.svelte";
  import Hinweis from "./Hinweis.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";
  import Zaehler from "./Zaehler.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let auftrag = $state<Auftragsstand | null>(null);
  let geladen = $state(false);

  async function runde(): Promise<boolean> {
    const a = (await ladeAuftraege()).find((x) => x.art === "pruefung") ?? null;
    auftrag = a;
    geladen = true;
    if (a?.stand === "fertig" && !schritt.weiter) await einrichtung.laden();
    // Vor dem Beginn (Umzug: erst kopieren) fragt der Takt weiter, bis die Prüfung beginnt
    return !a || !a.stand || laeuftNoch(a);
  }

  const halt = imTakt(runde, 1500);
  onDestroy(halt);

  async function beginne() {
    auftrag = await beginnePruefung(false);
  }

  let laeuft = $derived(laeuftNoch(auftrag));
  let fertig = $derived(auftrag?.stand === "fertig");
</script>

<Schrittrahmen zurueck={laeuft ? "gesperrt" : true} weiter={{ gesperrt: !fertig, titel: fertig ? undefined : "Erst nach der Prüfung" }}>
  <p class="klein">Die App sucht jedes Original. Fehlende sucht sie über die Prüfsumme in der Kellerwolke.</p>
  {#if !geladen}
    <Zustand art="laedt" text="Stand der Prüfung wird geholt" />
  {:else if !auftrag?.stand}
    <p class="leise">Die Prüfung hat noch nicht begonnen.</p>
    <div class="reihe"><Knopf text="Prüfung beginnen" symbol="stethoscope" haupt onclick={() => void einrichtung.tu(beginne, "Prüfung nicht begonnen")} /></div>
  {:else}
    <Auftragsfeld {auftrag} wort="geprüft" onneu={(a) => (auftrag = a)} />
    <Zaehler werte={[
      ["gut", teilwert(auftrag, "erreichbar"), "erreichbar"],
      ["warn", teilwert(auftrag, "wiedergefunden"), "über die Prüfsumme gefunden"],
      ["schlecht", teilwert(auftrag, "fehlt"), fertig ? "fehlen" : "fehlen bisher"],
    ]} />
    {#if laeuft}<Hinweis />{/if}
  {/if}
</Schrittrahmen>
