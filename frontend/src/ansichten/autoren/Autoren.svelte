<script lang="ts">
  import { onMount } from "svelte";
  import { loescheVerwaiste, resyncAutoren } from "../../lib/api/authors";
  import { anzahl, zahl } from "../../lib/format";
  import { rollstand } from "../../lib/rollstand";
  import Schnellfilterchip from "../../lib/schale/Schnellfilterchip.svelte";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import { autorenabgleich } from "../../lib/stand/autorenabgleich.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import { schnellfilter } from "../../lib/stand/schnellfilter.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Nachlader from "../../lib/teile/Nachlader.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Abgleich from "./Abgleich.svelte";
  import Autorbild from "./Autorbild.svelte";
  import { lebensdaten } from "./angaben";
  import { autorenansicht as ansicht, autorenfilter, autorsortierungen, type Autorsortierung } from "./liste.svelte";

  const WARTE_MS = 300;
  let uhr: ReturnType<typeof setTimeout> | undefined;
  let abgleichOffen = $state(autorenabgleich.laeuft || autorenabgleich.fertig);
  let laeuft = $state<"" | "neu" | "verwaist">("");

  let s = $derived(ansicht.statistik);
  let zeigeAbgleich = $derived(abgleichOffen || autorenabgleich.laeuft);
  let offen = $derived(s ? s.gesamt - s.mit_eintrag : 0);

  onMount(() => {
    void (ansicht.geladen ? ansicht.auffrischen() : ansicht.laden());
    return bestand.beiAenderung(() => void ansicht.auffrischen());
  });
  $effect(() => schnellfilter.biete(autorenfilter));

  function sucht() {
    clearTimeout(uhr);
    uhr = setTimeout(() => ansicht.filtere(ansicht.suche), WARTE_MS);
  }

  function pfeil(nach: Autorsortierung): string {
    if (nach !== ansicht.sortierung) return "";
    return ansicht.richtung === "asc" ? "arrow-up-short-wide" : "arrow-down-wide-short";
  }

  async function bildeNeu() {
    const ja = await frage({
      titel: "Autoren aus den Büchern neu bilden?",
      folgen: [
        `Autoren ohne Eintrag in Lexikon oder Normdatei${s ? ` (${zahl(offen)})` : ""} werden gelöscht und aus den Angaben der Bücher neu angelegt.`,
        "Von Hand eingetragene Lebensdaten und Biografien dieser Autoren gehen dabei verloren.",
        `Autoren mit Eintrag${s ? ` (${zahl(s.mit_eintrag)})` : ""} bleiben mit Foto, Biografie und Verweisen erhalten.`,
      ],
      ja: "Neu bilden",
      symbol: "users-gear",
    });
    if (!ja) return;
    laeuft = "neu";
    try {
      const e = await resyncAutoren();
      melde.gut(`${anzahl(e.gesamt, "Autor", "Autoren")}, davon ${zahl(e.neu_angelegt)} neu, aus ${anzahl(e.buecher_verarbeitet, "Buch", "Büchern")}`);
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht neu gebildet");
    } finally {
      laeuft = "";
    }
  }

  async function loescheVerwaisteAutoren() {
    const ja = await frage({
      titel: "Autoren ohne Buch löschen?",
      folgen: ["Alle Autoren, zu denen kein Buch mehr gehört, verschwinden mit Foto, Biografie und Werkliste.", "Bücher ändern sich nicht."],
      ja: "Verwaiste löschen",
    });
    if (!ja) return;
    laeuft = "verwaist";
    try {
      const e = await loescheVerwaiste();
      if (e.gelöscht) melde.gut(`${anzahl(e.gelöscht, "Autor", "Autoren")} gelöscht: ${e.autoren.slice(0, 5).join(", ")}${e.gelöscht > 5 ? ` und ${e.gelöscht - 5} weitere` : ""}`);
      else melde.info("Jeder Autor hat mindestens ein Buch");
      if (e.gelöscht) bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    } finally {
      laeuft = "";
    }
  }
</script>

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  <h1>Autoren</h1>
  {#if s}<span class="leise zahl">{zahl(s.gesamt)}, davon {zahl(s.mit_eintrag)} mit Eintrag</span>{/if}
  <span class="reihe schiebt">
    <Knopf text="Lexikon abgleichen" symbol="arrows-rotate" klein aufgeklappt={zeigeAbgleich} onclick={() => (abgleichOffen = !abgleichOffen)} />
    <Knopf text="Aus den Büchern neu bilden" symbol="users-gear" klein laeuft={laeuft === "neu"} gesperrt={autorenabgleich.laeuft} onclick={() => void bildeNeu()} />
  </span>
</div>

<div class="inhalt rollen" use:rollstand={"/authors"}>
  <div class="reihe">
    <!-- Als Schnellfilter übernimmt das Suchfeld die Suche nach dem Namen -->
    {#if schnellfilter.filtert}<Schnellfilterchip ziel={autorenfilter} />{:else}<input class="eingabe autorensuche" type="search" placeholder="Autor suchen" aria-label="Autor suchen" bind:value={ansicht.suche} oninput={sucht} />{/if}
    {#each autorsortierungen as [nach, text] (nach)}<Chip {text} symbol={pfeil(nach)} titel="Nach {text} sortieren, noch einmal dreht die Richtung" gedrueckt={ansicht.sortierung === nach} onclick={() => ansicht.sortiere(nach)} />{/each}
    <span class="reihe schiebt">
      {#if s}<span class="leise zahl">{zahl(s.mit_foto)} mit Foto, {zahl(s.mit_biografie)} mit Biografie{offen ? `, ${zahl(offen)} offen` : ""}</span>{/if}
      <Knopf text="Verwaiste löschen" symbol="broom" klein frei laeuft={laeuft === "verwaist"} gesperrt={autorenabgleich.laeuft} titel="Autoren löschen, zu denen kein Buch mehr gehört" onclick={() => void loescheVerwaisteAutoren()} />
    </span>
  </div>
  {#if zeigeAbgleich}<Abgleich onzu={() => (abgleichOffen = false)} />{/if}

  {#if ansicht.fehler}
    <Zustand art="fehler" text={ansicht.fehler} onerneut={() => void ansicht.laden()} />
  {:else if !ansicht.geladen}
    <Zustand art="laedt" text="Autoren werden geladen" />
  {:else if !ansicht.autoren.length}
    <Zustand text={ansicht.suche.trim() ? `Kein Autor heißt wie "${ansicht.suche.trim()}".` : "Noch keine Autoren. Sie entstehen aus den Angaben der Bücher."}>
      {#if ansicht.suche.trim()}<Knopf text={schnellfilter.filtert ? "Filter leeren" : "Suche leeren"} symbol="xmark" klein onclick={() => schnellfilter.leere(autorenfilter)} />{/if}
    </Zustand>
  {/if}

  {#if ansicht.autoren.length}
    <div class="autorengitter">
      {#each ansicht.autoren as autor (autor.id)}
        <a class="autorkarte platte" href="/author/{autor.id}">
          <Autorbild {autor} />
          <span><b>{autor.name}</b><span class="leise zahl">{anzahl(autor.book_count, "Buch", "Bücher")}{lebensdaten(autor) ? `, ${lebensdaten(autor)}` : ""}</span></span>
        </a>
      {/each}
    </div>
    <Nachlader geladen={ansicht.autoren.length} gesamt={ansicht.gesamt} laedt={ansicht.laedt} onmehr={() => void ansicht.mehr()} />
  {/if}
</div>
