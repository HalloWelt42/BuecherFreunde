<script lang="ts">
  // Rückfrage vor dem Übersetzen (BF-71, Entwurf Abschnitt 2): Umfang, Dauer mit Uhrzeit, Ablauf, Rechner, was englisch
  // bleibt, Abbildungen, Ablage, dazu die Anrede (du oder Sie). Geht es nicht, steht der Grund statt der Taste.
  import { holeFolgen, starteUebersetzung } from "../../lib/api/uebersetzung";
  import { navigate } from "../../lib/router.svelte";
  import { anzahl, zahl } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { uebersetzungen } from "../../lib/stand/uebersetzungen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import type { Anrede, Folgen } from "../../lib/uebersetzung/typen";
  import { gegen, ungefaehr } from "../../lib/uebersetzung/zeiten";

  let { buch, onschliessen, ongestartet }: { buch: BuchEinzeln; onschliessen: () => void; ongestartet: () => void } = $props();

  let folgen = $state<Folgen | null>(null);
  let fehler = $state("");
  let startet = $state(false);
  let anrede = $state<Anrede>("du");
  const ANREDEN: [Anrede, string][] = [["du", "du"], ["Sie", "Sie"]];

  async function lade() {
    fehler = "";
    try {
      folgen = await holeFolgen(buch.id, "de");
      anrede = folgen.anrede ?? "du";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade());

  let zeilen = $derived.by((): [string, string][] => {
    const f = folgen;
    if (!f?.geht) return [];
    const ablage = f.ablage?.ort === "kellerwolke" ? "in der Kellerwolke neben dem Original unter Fassungen/de" : "neben dem Original unter Fassungen/de";
    return ([
      ["Buch", [buch.title, anzahl(f.seiten, "Seite", "Seiten"), anzahl(f.kapitel, "Kapitel", "Kapitel")].join(", ")],
      ["Dauer", `${ungefaehr(f.dauer_s)} mit Prüfung, fertig ${gegen(f.fertig_gegen)}, wenn du jetzt startest; geschätzt aus ${zahl(Math.round(f.tempo_s_je_seite))} Sekunden je Seite`],
      ["Ablauf", "Zerlegen, Begriffe, Übersetzen, Prüfen, Nacharbeit, Setzen; Kapitel für Kapitel, fertige sofort lesbar"],
      ["Rechner", "lokale KI über die Leitstelle, im Hintergrund hinter Vorlesen und Suche"],
      ["Bleibt englisch", `Code, Bezeichner, Fachbegriffe nach der Begriffsliste (${zahl(f.begriffe)})`],
      ["Abbildungen", f.abbildungen ? `${anzahl(f.abbildungen, "Bild", "Bilder")}, wie im Original` : ""],
      ["Ablage", `${ablage}, das Original bleibt unverändert`],
    ] as [string, string][]).filter(([, w]) => w);
  });

  async function starte() {
    startet = true;
    try {
      await starteUebersetzung(buch.id, "de", anrede);
      melde.gut("Übersetzung läuft");
      uebersetzungen.angestossen();
      ongestartet();
    } catch (e) {
      melde.schlecht(e, "Nicht gestartet");
    } finally {
      startet = false;
    }
  }

  function begriffe() {
    onschliessen();
    navigate(`/book/${buch.id}/begriffe`);
  }
</script>

<Fenster titel="Ins Deutsche übersetzen?" breite="36rem" {onschliessen}>
  {#if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
  {:else if !folgen}
    <Zustand art="laedt" text="Umfang wird ermittelt" />
  {:else if !folgen.geht}
    <p class="marke-text warn"><Symbol name="circle-exclamation" />{folgen.grund}</p>
  {:else}
    <dl class="angaben uebersetzungsfrage">{#each zeilen as [feld, wert] (feld)}<dt>{feld}</dt><dd title={feld === "Ablage" ? folgen.ablage?.pfad : undefined}>{wert}</dd>{/each}
      <dt>Anrede</dt><dd class="reihe"><Segment name="Anrede" werte={ANREDEN} wert={anrede} gesperrt={startet} onwahl={(a) => (anrede = a)} /><span class="leise">So spricht das übersetzte Buch dich an</span></dd>
    </dl>
  {/if}
  {#snippet fuss()}
    {#if folgen?.geht}
      <Knopf text="Übersetzen" symbol="language" haupt laeuft={startet} onclick={() => void starte()} />
      <Knopf text="Begriffe ansehen" symbol="spell-check" gesperrt={startet} onclick={begriffe} />
      <span class="schiebt"><Knopf text="Abbrechen" frei onclick={onschliessen} /></span>
    {:else}
      <span class="schiebt"><Knopf text="Schließen" onclick={onschliessen} /></span>
    {/if}
  {/snippet}
</Fenster>
