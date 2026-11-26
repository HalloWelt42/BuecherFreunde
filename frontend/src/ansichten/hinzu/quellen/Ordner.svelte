<script lang="ts">
  // Einen Ordner einlesen: erst zeigen, was darin liegt, dann übernehmen
  import { ladePfade } from "../../../lib/api/config";
  import { einlesenVorschau, scanneExternesVerzeichnis, scanneImportVerzeichnis, type Einlesevorschau } from "../../../lib/api/imports";
  import { anzahl, formatName, groesse, zahl } from "../../../lib/format";
  import { annahme } from "../../../lib/stand/annahme.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { quelle }: { quelle: "import" | "extern" } = $props();

  const HOECHSTENS = 60;
  const texte = {
    import: { titel: "Eingangsordner", symbol: "folder-open", text: "Dateien aus dem Eingangsordner werden in die Bibliothek kopiert und bleiben im Ordner liegen. Was schon da ist, wird übersprungen." },
    extern: { titel: "Alte Sammlung einlesen", symbol: "hard-drive", text: "Für Laufwerke und Netzordner. Gelesen wird nur: die Originale bleiben unangetastet, die Bibliothek bekommt Kopien. Was schon da ist, wird übersprungen." },
  };

  let pfad = $state("");
  let anreichern = $state(false);
  let vorschau = $state<Einlesevorschau | null>(null);
  let prueft = $state(false);
  let liest = $state(false);
  let fehler = $state("");

  let t = $derived(texte[quelle]);
  let neu = $derived(vorschau?.dateien.filter((d) => !d.ist_duplikat).length ?? 0);

  $effect(() => {
    ladePfade().then((p) => (pfad = (quelle === "import" ? p.import : p.extern) ?? "")).catch(() => {});
  });

  async function zeigeVorschau() {
    prueft = true;
    fehler = "";
    try {
      vorschau = await einlesenVorschau(quelle);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      prueft = false;
    }
  }

  async function lies() {
    liest = true;
    fehler = "";
    try {
      const e = await (quelle === "import" ? scanneImportVerzeichnis : scanneExternesVerzeichnis)(anreichern);
      if (e.gefunden) melde.gut(`${anzahl(e.gefunden, "Datei", "Dateien")} gefunden, Fortschritt unten und bei den Aufträgen`);
      else melde.info("Im Ordner liegt nichts, was sich einlesen lässt");
      vorschau = null;
      await annahme.auffrischen();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      liest = false;
    }
  }
</script>

<Karte titel={t.titel} symbol={t.symbol}>
  <p>{t.text}</p>
  {#if pfad}<p class="leise pfad">{pfad}</p>{/if}
  <div class="reihe">
    <Haekchen text="Angaben ergänzen, dauert länger" an={anreichern} onwahl={(an) => (anreichern = an)} />
    <span class="reihe schiebt">
      <Knopf text="Vorschau zeigen" symbol="eye" klein laeuft={prueft} gesperrt={liest} onclick={() => void zeigeVorschau()} />
      <Knopf text={vorschau ? `${anzahl(neu, "neue Datei", "neue Dateien")} einlesen` : "Einlesen"} symbol="file-import" klein haupt laeuft={liest} gesperrt={prueft || (vorschau !== null && neu === 0)} onclick={() => void lies()} />
    </span>
  </div>
  {#if prueft}<p class="leise">Dateien werden verglichen, bei großen Ordnern dauert das etwas.</p>{/if}
  {#if fehler}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />{fehler}</p>{/if}
  {#if vorschau}
    <p class="zahl">{zahl(neu)} neu, {zahl(vorschau.dateien.length - neu)} schon in der Bibliothek</p>
    {#if vorschau.dateien.length}
      <ul class="dateien">
        {#each vorschau.dateien.slice(0, HOECHSTENS) as d (d.pfad)}
          <li><span class="name" title={d.pfad}>{d.name}</span><span class="leise zahl">{formatName(d.format)}, {groesse(d.groesse)}</span>{#if d.ist_duplikat}<span class="marke-text info"><Symbol name="clone" />gibt es schon{d.bestehendes_buch && d.bestehendes_buch !== d.name ? `: ${d.bestehendes_buch}` : ""}</span>{:else}<span class="marke-text gut"><Symbol name="plus" />neu</span>{/if}</li>
        {/each}
      </ul>
      {#if vorschau.dateien.length > HOECHSTENS}<p class="leise zahl">und {zahl(vorschau.dateien.length - HOECHSTENS)} weitere</p>{/if}
    {/if}
  {/if}
</Karte>

<style>
  .pfad {
    overflow-wrap: anywhere;
  }
  .dateien {
    display: grid;
    max-height: 18rem;
    overflow: auto;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.125rem 0.75rem;
    align-items: baseline;
    padding: 0.375rem 0;
    border-top: 1px solid var(--linie);
  }
  .name {
    flex: 1 1 14rem;
    min-width: 0;
    overflow-wrap: anywhere;
  }
</style>
