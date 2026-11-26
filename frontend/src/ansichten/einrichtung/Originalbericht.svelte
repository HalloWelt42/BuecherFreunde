<script lang="ts">
  // Bericht nach dem Wiederherstellen oder dem Umzug: was erreichbar ist, was über die Prüfsumme wiedergefunden wurde (der neue
  // Ort ist eingetragen) und was fehlt. Fehlende bleiben im Bestand, mit Hinweis am Buch. Gelöscht wird nichts.
  import { download } from "../../lib/api/client";
  import { beginnePruefung, ladePruefbericht, PRUEFBERICHT_DATEI, type Befund, type Pruefbericht } from "../../lib/api/einrichtung";
  import { zahl } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Deckblatt from "../../lib/teile/Deckblatt.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";
  import Zaehler from "./Zaehler.svelte";

  /** So viele je Gruppe; der ganze Bericht steht in der Datei */
  const ZEIGEN = 3;

  let bericht = $state<Pruefbericht | null>(null);
  let fehler = $state("");

  async function lade() {
    try {
      bericht = await ladePruefbericht();
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade());

  let fehlen = $derived(bericht?.eintraege.filter((e) => e.ergebnis === "fehlt") ?? []);
  let wieder = $derived(bericht?.eintraege.filter((e) => e.ergebnis === "wiedergefunden") ?? []);

  async function herunterladen() {
    try {
      const adresse = URL.createObjectURL(await download(PRUEFBERICHT_DATEI));
      Object.assign(document.createElement("a"), { href: adresse, download: "pruefbericht.json" }).click();
      setTimeout(() => URL.revokeObjectURL(adresse), 10_000);
    } catch (e) {
      melde.schlecht(e, "Bericht nicht geladen");
    }
  }

  async function erneut() {
    await beginnePruefung(false);
    einrichtung.zeige("pruefung");
  }
</script>

{#snippet gruppe(symbol: string, text: string, liste: Befund[], wann: string)}
  <section class="ew-buecher">
    <h3 class="ew-gruppe-kopf"><Symbol name={symbol} />{text} <span class="leise zahl">{zahl(liste.length)}</span></h3>
    {#each liste.slice(0, ZEIGEN) as b (b.buch_id)}
      <div class="ew-buchzeile">
        <span class="umschlag"><Deckblatt buch={{ id: b.buch_id, title: b.titel, author: b.autor }} /></span>
        <span class="ew-mitte"><b>{b.titel}</b>{#if b.autor}<small>{b.autor}</small>{/if}{#if b.pfad}<small>{wann} <code class="pfad">{b.pfad}</code></small>{/if}{#if b.text}<small>{b.text}</small>{/if}</span>
      </div>
    {/each}
    {#if liste.length > ZEIGEN}<p class="leise zahl">und {zahl(liste.length - ZEIGEN)} weitere</p>{/if}
  </section>
{/snippet}

<Schrittrahmen weiter={{ text: "Zur Bibliothek", symbol: "book-bookmark", tun: () => einrichtung.abschliessen() }}>
  {#if bericht}
    <Zaehler werte={[["gut", bericht.erreichbar, "erreichbar"], ["warn", bericht.wiedergefunden, "über die Prüfsumme wiedergefunden"], ["schlecht", bericht.fehlt, "fehlen"]]} />
    <p class="marke-text info"><Symbol name="shield-halved" />Nichts gelöscht. Fehlende bleiben im Bestand, mit Hinweis am Buch.</p>
    {#if fehlen.length}{@render gruppe("circle-xmark", "Fehlen", fehlen, "zuletzt")}{/if}
    {#if wieder.length}{@render gruppe("fingerprint", "Wiedergefunden", wieder, "jetzt")}{/if}
    <div class="ew-tasten2">
      <Knopf text="Bericht herunterladen" symbol="download" klein onclick={() => void herunterladen()} />
      <Knopf text="Erneut prüfen" symbol="rotate-right" klein gesperrt={einrichtung.arbeitet} onclick={() => void einrichtung.tu(erneut, "Prüfung nicht begonnen")} />
    </div>
  {:else if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
  {:else}
    <Zustand art="laedt" text="Bericht wird geholt" />
  {/if}
</Schrittrahmen>
