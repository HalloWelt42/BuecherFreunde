<script lang="ts">
  // Schritt Originale (Umzug ohne Kellerwolke): "Originale kopieren" holt sie über das Netz als Auftrag mit Prüfsummen, "Ort
  // übernehmen" prüft nur die umgehängte Platte. Weiter geht es schon, während kopiert wird.
  import { onDestroy, untrack } from "svelte";
  import { ladeAuftraege, waehleOriginale, type Auftragsstand, type Schritt } from "../../lib/api/einrichtung";
  import { laeuftNoch, teilwert } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { groesse, vonGesamt } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Auftragsfeld from "./Auftragsfeld.svelte";
  import Hinweis from "./Hinweis.svelte";
  import Kachel from "./Kachel.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  type Weg = "kopieren" | "ort";
  /** Nach einem Neustart der Seite: der Server nennt die Wahl im Text des Schritts */
  let weg = $state<Weg | null>(untrack(() => (schritt.stand !== "erledigt" ? null : schritt.text.startsWith("Ort") ? "ort" : "kopieren")));
  let auftrag = $state<Auftragsstand | null>(null);
  let halt: (() => void) | null = null;

  function beobachte(art: "kopieren" | "pruefung") {
    halt?.();
    halt = imTakt(async () => {
      auftrag = (await ladeAuftraege()).find((a) => a.art === art) ?? null;
      return laeuftNoch(auftrag);
    }, 1500);
  }

  $effect(() => {
    if (weg) untrack(() => beobachte(weg === "kopieren" ? "kopieren" : "pruefung"));
  });
  onDestroy(() => halt?.());

  async function waehle(neu: Weg) {
    auftrag = await waehleOriginale(neu);
    weg = neu;
    await einrichtung.laden();
  }

  /** "1.802 von 4.731 Originalen, 61 GB von 160 GB, Prüfsummen stimmen" */
  let zeile = $derived.by(() => {
    if (!auftrag) return "";
    const g = auftrag.teile.find((t) => t.schluessel === "groesse");
    const falsch = teilwert(auftrag, "fehler");
    return [
      `${vonGesamt(auftrag.fertig, auftrag.gesamt)} Originalen`,
      g?.gesamt ? `${groesse(g.fertig)} von ${groesse(g.gesamt)}` : "",
      falsch ? `${falsch} mit falscher Prüfsumme` : "Prüfsummen stimmen",
    ].filter(Boolean).join(", ");
  });
</script>

<Schrittrahmen weiter={{ gesperrt: schritt.stand !== "erledigt", titel: schritt.stand === "erledigt" ? undefined : "Erst wählen, wie die Originale kommen" }}>
  <p class="klein">Das alte Gerät hat keine Kellerwolke. Wie kommen die Originale her?</p>
  <div class="ew-kacheln">
    <Kachel symbol="copy" farbe="#2f6fb3" titel="Originale kopieren" text="Über das Netz, als Auftrag mit Prüfsummen. Lässt sich unterbrechen und fortsetzen." pfeil={false}
      gedrueckt={weg === "kopieren"} gesperrt={!!weg || einrichtung.arbeitet} onclick={() => void einrichtung.tu(() => waehle("kopieren"), "Nicht begonnen")} />
    <Kachel symbol="hard-drive" farbe="#a87a2a" titel="Ort übernehmen" text="Die Platte ist umgehängt. Das Gerät prüft nur, ob alles da ist." pfeil={false}
      gedrueckt={weg === "ort"} gesperrt={!!weg || einrichtung.arbeitet} onclick={() => void einrichtung.tu(() => waehle("ort"), "Nicht begonnen")} />
  </div>
  {#if weg === "ort"}<p class="leise">Die Platte des alten Geräts hängt am neuen als Ort Volltexte (siehe Speicherorte). Geprüft wird jedes Original mit seiner Prüfsumme.</p>{/if}
  {#if auftrag?.stand}
    <Auftragsfeld {auftrag} wort="geprüft" zeile={weg === "kopieren" ? zeile : ""} onneu={(a) => (auftrag = a)} />
    {#if laeuftNoch(auftrag)}<Hinweis text="Läuft weiter, wenn du die Seite schließt. Nach einer Unterbrechung geht es an derselben Stelle weiter." />{/if}
  {/if}
</Schrittrahmen>
