<script lang="ts">
  // Bibliothek ergänzen: was fehlt, gezielt nachholen. Erst die Vorschau, dann der Auftrag.
  import { rescanKategorien, rescanVorschau, starteRescan, type Ergaenzungsart, type Ergaenzungsregal, type Ergaenzungsvorschau } from "../../../lib/api/imports";
  import { anzahl, zahl } from "../../../lib/format";
  import { auftraege } from "../../../lib/stand/auftraege.svelte";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Ergaenzungsstand from "./Ergaenzungsstand.svelte";
  import { ARTEN, betroffen, regalwerte } from "./ergaenzung";

  let gewaehlt = $state<Ergaenzungsart[]>(["cover", "isbn"]);
  let manuell = $state(false);
  let regal = $state("");
  let zahlen = $state<Ergaenzungsvorschau | null>(null);
  let summe = $state<Ergaenzungsvorschau | null>(null);
  let regale = $state<Ergaenzungsregal[]>([]);
  let fehler = $state("");
  let fenster = $state(false);
  let startet = $state(false);

  let regalnummer = $derived(regal === "" ? null : Number(regal));
  let n = $derived(betroffen(summe, gewaehlt, regalnummer, regale));
  let laeuft = $derived(auftraege.ergaenzung.laeuft);

  $effect(() => {
    void zaehle(gewaehlt, regalnummer, manuell);
  });
  $effect(() => bestand.beiAenderung(() => void zaehle(gewaehlt, regalnummer, manuell)));

  async function zaehle(arten: Ergaenzungsart[], nummer: number | null, mitManuellen: boolean) {
    try {
      const [alle, teil, liste] = await Promise.all([
        rescanVorschau(ARTEN.map((a) => a.art), nummer, mitManuellen),
        arten.length ? rescanVorschau(arten, nummer, mitManuellen) : null,
        arten.length ? rescanKategorien(arten, mitManuellen) : [],
      ]);
      zahlen = alle;
      summe = teil;
      regale = liste;
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  function schalte(art: Ergaenzungsart) {
    gewaehlt = gewaehlt.includes(art) ? gewaehlt.filter((a) => a !== art) : [...gewaehlt, art];
  }

  async function starte() {
    startet = true;
    try {
      const e = await starteRescan(gewaehlt, regalnummer, manuell);
      if (e.gestartet) melde.gut(`${anzahl(e.anzahl ?? 0, "Buch wird", "Bücher werden")} geprüft`);
      else melde.info("Kein Buch, dem davon etwas fehlt, oder es läuft schon ein Durchgang");
      fenster = false;
      await auftraege.auffrischen();
    } catch (e) {
      melde.schlecht(e, "Nicht gestartet");
    } finally {
      startet = false;
    }
  }
</script>

<Karte titel="Bibliothek ergänzen" symbol="arrows-rotate">
  <div class="reihe">
    {#each ARTEN as a (a.art)}<Chip text={a.text} zahl={zahlen ? zahl(zahlen.typen[a.art] ?? 0) : undefined} titel={a.was} gedrueckt={gewaehlt.includes(a.art)} gesperrt={laeuft} onclick={() => schalte(a.art)} />{/each}
    <Chip text="Von Hand Bearbeitete einschließen" gedrueckt={manuell} gesperrt={laeuft} titel="Sonst bleiben Bücher außen vor, deren Angaben von Hand geändert wurden" onclick={() => (manuell = !manuell)} />
    {#if regale.length}<Auswahl name="Regal" klein werte={regalwerte(regale)} wert={regal} gesperrt={laeuft} onwahl={(w) => (regal = w)} />{/if}
    <span class="schiebt"><Knopf text="Vorschau zeigen" symbol="eye" klein gesperrt={!gewaehlt.length || laeuft} onclick={() => (fenster = true)} /></span>
  </div>
  {#if fehler}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />{fehler}</p>{/if}
  {#if laeuft || auftraege.ergaenzungFertig}<Ergaenzungsstand />{/if}
</Karte>

{#if fenster}
  <Fenster titel="Vorschau, noch ist nichts geändert" onschliessen={() => (fenster = false)}>
    <p><b class="zahl">{n ? anzahl(n, "Buch", "Bücher") : "Kein Buch"}</b>{n === 1 ? " kommt" : " kommen"} dran{regalnummer !== null ? `, nur ${regalnummer === 0 ? "ohne Regal" : (bestand.regal(regalnummer)?.name ?? "dieses Regal")}` : ""}{manuell ? ", auch von Hand bearbeitete" : ", von Hand bearbeitete bleiben außen vor"}.</p>
    <ul class="vorschau-liste">
      {#each ARTEN.filter((a) => gewaehlt.includes(a.art)) as a (a.art)}
        <li><Symbol name={a.symbol} /><span><b>{a.text}</b> <span class="leise zahl">{zahl(summe?.typen[a.art] ?? 0)} {a.art === "volltext" ? "zu prüfen" : "offen"}</span><br />{a.was}</span></li>
      {/each}
    </ul>
    <p class="leise">Vorhandene Umschläge, ISBN und Texte bleiben, wie sie sind. Der Auftrag läuft im Hintergrund und lässt sich anhalten.</p>
    {#snippet fuss()}
      <span class="schiebt reihe">
        <Knopf text="Abbrechen" onclick={() => (fenster = false)} />
        <Knopf text="Starten" symbol="play" haupt laeuft={startet} gesperrt={!n} onclick={() => void starte()} />
      </span>
    {/snippet}
  </Fenster>
{/if}

<style>
  .vorschau-liste {
    display: grid;
    gap: 0.625rem;
  }
  .vorschau-liste li {
    display: grid;
    grid-template-columns: 1.5rem minmax(0, 1fr);
    gap: 0.5rem;
  }
</style>
