<script lang="ts">
  // Reiter Hinzufügen (BF-80): je Weg "erst bestätigen" und die Grenzen für ZIP. Hochladen im Browser läuft immer über die
  // Vorschau, der Schalter steht fest; Eingangsordner und Ordner auf dem Gerät laufen ohne ihn wie bisher von selbst ins Regal.
  // Jede Änderung gilt sofort; was der Server nicht nimmt, steht danach wieder wie zuvor.
  import { ladeEingangsordner, ladeHinzufuegeeinstellungen, speichereHinzufuegeeinstellungen } from "../../lib/api/annahme";
  import type { Hinzufuegeeinstellungen } from "../../lib/annahme/vorschautypen";
  import { ladePfade } from "../../lib/api/config";
  import { ich } from "../../lib/stand/ich.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Schalter from "../../lib/teile/Schalter.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";

  type Grenze = keyof Hinzufuegeeinstellungen["zip"];
  /** Feld, Name und erlaubter Bereich, wie am Server (annahme/einstellungen.py, models/grenzen.py) */
  const GRENZEN: [Grenze, string, number, number][] = [
    ["dateien", "Dateien in einer ZIP, höchstens", 1, 100000],
    ["datei_mb", "Eine Datei ausgepackt, Megabyte", 1, 1048576],
    ["gesamt_mb", "Alles ausgepackt, Megabyte", 1, 1048576],
    ["tiefe", "Ordner ineinander, höchstens", 1, 64],
    ["verhaeltnis", "Stärker gepackt als so viel zu 1 nicht", 1, 10000],
  ];

  let werte = $state<Hinzufuegeeinstellungen | null>(null);
  let fehler = $state("");
  let speichert = $state(false);
  let eingang = $state("");
  let einlesen = $state("");

  async function laden() {
    try {
      werte = await ladeHinzufuegeeinstellungen();
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => {
    void laden();
    if (ich.darf("hinzufuegen")) ladeEingangsordner().then((o) => (eingang = `${o.ort === "kellerwolke" ? "Kellerwolke" : "Auf dem Gerät"}, ${o.pfad}`)).catch(() => {});
    ladePfade().then((p) => (einlesen = p.import ?? "")).catch(() => {});
  });

  async function speichere(neu: Hinzufuegeeinstellungen) {
    speichert = true;
    try {
      werte = await speichereHinzufuegeeinstellungen(neu);
      melde.gut("Gespeichert");
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
      await laden();
    } finally {
      speichert = false;
    }
  }

  function setzeWeg(weg: "eingangsordner" | "ordner", an: boolean) {
    if (werte) void speichere({ ...werte, bestaetigen: { ...werte.bestaetigen, [weg]: an } });
  }

  function setzeGrenze(feld: Grenze, roh: string, von: number, bis: number) {
    if (!werte) return;
    const zahl = Number(roh);
    if (!Number.isInteger(zahl) || zahl < von || zahl > bis) {
      melde.warn(`Erlaubt sind ganze Zahlen von ${von.toLocaleString("de-DE")} bis ${bis.toLocaleString("de-DE")}`);
      werte = { ...werte };
      return;
    }
    if (zahl !== werte.zip[feld]) void speichere({ ...werte, zip: { ...werte.zip, [feld]: zahl } });
  }
</script>

{#if fehler && !werte}
  <Zustand art="fehler" text={fehler} onerneut={() => void laden()} />
{:else if !werte}
  <Zustand art="laedt" text="Einstellungen werden geladen" />
{:else}
  {@const w = werte}
  <div class="raster">
    <Karte titel="Erst bestätigen" symbol="list-check">
      <div>
        <div class="wegzeile"><Symbol name="cloud-arrow-up" /><span>Hochladen im Browser<small>einzeln, mehrere, ZIP: immer mit Vorschau</small></span><Schalter an name="Hochladen im Browser erst bestätigen" gesperrt onwahl={() => {}} /></div>
        <div class="wegzeile"><Symbol name="folder-open" /><span>Eingangsordner{#if eingang}<small class="pfad">{eingang}</small>{/if}</span><Schalter an={w.bestaetigen.eingangsordner} name="Eingangsordner erst bestätigen" gesperrt={speichert} onwahl={(an) => setzeWeg("eingangsordner", an)} /></div>
        <div class="wegzeile"><Symbol name="hard-drive" /><span>Ordner auf dem Gerät<small class="pfad">{einlesen || "Einlese-Ordner und externe Sammlung"}</small></span><Schalter an={w.bestaetigen.ordner} name="Ordner auf dem Gerät erst bestätigen" gesperrt={speichert} onwahl={(an) => setzeWeg("ordner", an)} /></div>
      </div>
      <p class="leise">Aus: von selbst ins Regal, wie bisher.</p>
    </Karte>
    <!-- Hier folgt die Karte "Fehlende Bände" mit der Suchadresse (BF-75), wie im Entwurf rechts neben "Erst bestätigen" -->
    <Karte titel="Grenzen für ZIP" symbol="file-zipper">
      <div class="zweifeld">
        {#each GRENZEN as [feld, name, von, bis] (feld)}
          <label class="feld"><span>{name}</span><input class="eingabe zahl" type="number" min={von} max={bis} step="1" value={w.zip[feld]} disabled={speichert} onchange={(e) => setzeGrenze(feld, e.currentTarget.value, von, bis)} /></label>
        {/each}
      </div>
      <p class="leise">Liegt eine ZIP über einer Grenze, wird sie oder der eine Eintrag nicht ausgepackt und steht mit Grund in der Vorschau.</p>
    </Karte>
  </div>
{/if}
