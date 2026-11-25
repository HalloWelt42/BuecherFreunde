<script lang="ts">
  // Angaben aus den Quellen vergleichen und übernehmen; dazu Buchtext, KI-Vorschlag und neuer Umschlag
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { coverUrl, umschlagNeu } from "../../lib/api/books";
  import { sucheMetadaten, uebernehmMetadaten } from "../../lib/api/metadata";
  import { anzahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { quellen as alleQuellen } from "../../lib/stand/quellen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Vergleichstabelle, { type Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Beschreibungstext from "./Beschreibungstext.svelte";
  import Kivorschlag from "./Kivorschlag.svelte";
  import Rohdaten from "./Rohdaten.svelte";
  import { ALLE, fundart, nutzlast, vergleiche, type Quelle, type Vorschlag } from "./angaben";

  let { buch, ongeaendert }: { buch: BuchEinzeln; ongeaendert: () => void } = $props();

  let quellen = $derived<[Quelle, string][]>([...(alleQuellen.buecher.length > 1 ? [[ALLE, "Alle"] as [Quelle, string]] : []), ...alleQuellen.buecher.map((q) => [q.kennung, q.name] as [Quelle, string])]);
  let quelle = $state<Quelle>("");
  let sucht = $state(false);
  let speichert = $state(false);
  let holtUmschlag = $state(false);
  let hinweis = $state("");
  let nebenbei = $state<string[]>([]);
  let vorschlag = $state<Vorschlag | null>(null);
  let zeilen = $state<Vergleichszeile[]>([]);
  let listen = $state<string[]>([]);
  let textOffen = $state(false);
  let kiOffen = $state(false);

  let gewaehlt = $derived(zeilen.filter((z) => z.gewaehlt && !z.gleich).map((z) => z.schluessel));
  let zahlGewaehlt = $derived(gewaehlt.length + listen.length);
  let gefunden = $derived(vorschlag ? fundart(vorschlag) : null);

  $effect(() => void alleQuellen.bereit());

  function verwirf() {
    vorschlag = null;
    zeilen = [];
    listen = [];
    quelle = "";
    hinweis = "";
    nebenbei = [];
  }

  async function suche(neu: Quelle) {
    verwirf();
    quelle = neu;
    sucht = true;
    try {
      const a = await sucheMetadaten(buch.id, neu);
      nebenbei = a.angereichert ? (a.hinweise ?? []) : [];
      if (!a.angereichert || !a.vorschlag || !a.aktuell) {
        hinweis = a.grund ?? "Nichts gefunden.";
        return;
      }
      vorschlag = a.vorschlag;
      zeilen = vergleiche(a.vorschlag, a.aktuell, coverUrl(buch.id, buch.cover_stand || buch.updated_at), neu === ALLE ? alleQuellen.namen : {});
    } catch (e) {
      hinweis = e instanceof Error ? e.message : String(e);
    } finally {
      sucht = false;
    }
  }

  async function uebernimm() {
    if (!vorschlag) return;
    speichert = true;
    try {
      const e = await uebernehmMetadaten(buch.id, nutzlast(vorschlag, quelle, new Set(gewaehlt), new Set(listen)));
      if (e.hinweis) melde.warn(`Übernommen, Umschlag nicht: ${e.hinweis}`);
      else melde.gut("Übernommen");
      verwirf();
      bestand.geaendert();
      ongeaendert();
    } catch (e) {
      hinweis = e instanceof Error ? e.message : String(e);
    } finally {
      speichert = false;
    }
  }

  async function holeUmschlag() {
    holtUmschlag = true;
    try {
      await umschlagNeu(buch.id);
      melde.gut("Umschlag neu geholt");
      ongeaendert();
    } catch (e) {
      melde.schlecht(e, "Umschlag nicht geholt");
    } finally {
      holtUmschlag = false;
    }
  }

  function waehle(schluessel: string, an: boolean) {
    zeilen = zeilen.map((z) => (z.schluessel === schluessel ? { ...z, gewaehlt: an } : z));
  }
</script>

<Karte titel="Angaben vergleichen" symbol="code-compare" breit>
  <div class="reihe">
    {#if quellen.length}<Segment name="Quelle" werte={quellen} wert={quelle} gesperrt={sucht} onwahl={(q) => void suche(q)} />
    {:else if alleQuellen.geladen}<span class="leise">Keine Quelle eingeschaltet.</span>{/if}
    <span class="leise">{#if sucht}<Symbol name="circle-notch" dreht /> wird gesucht{:else}Nichts ändert sich vor dem Übernehmen.{/if}</span>
  </div>
  {#if hinweis}<p class="marke-text warn" role="status">{hinweis}</p>{/if}
  {#if vorschlag}
    {#if gefunden}<p class="marke-text {gefunden.ton}"><Symbol name={gefunden.ton === "gut" ? "circle-check" : "circle-question"} />{gefunden.text}</p>{/if}
    {#each nebenbei as grund (grund)}<p class="leise klein"><Symbol name="circle-info" /> {grund}</p>{/each}
    <Vergleichstabelle {zeilen} gesperrt={speichert} onwahl={waehle} />
    {#if vorschlag.raw && Object.keys(vorschlag.raw).length}<Rohdaten daten={vorschlag.raw} gewaehlt={listen} onwahl={(name, an) => (listen = an ? [...listen, name] : listen.filter((l) => l !== name))} />{/if}
  {/if}
  <div class="reihe">
    {#if vorschlag}
      <Knopf text={zahlGewaehlt ? `${anzahl(zahlGewaehlt, "Feld", "Felder")} übernehmen` : "Nichts gewählt"} symbol="check" haupt klein gesperrt={!zahlGewaehlt} laeuft={speichert} onclick={() => void uebernimm()} />
      <Knopf text="Verwerfen" symbol="xmark" klein onclick={verwirf} />
    {/if}
    <Knopf text="Aus dem Buchtext" symbol="book" klein aufgeklappt={textOffen} onclick={() => (textOffen = !textOffen)} />
    {#if anschluesse.jetzt.ki}<Knopf text="Vorschlag der KI" symbol="wand-magic-sparkles" klein onclick={() => (kiOffen = true)} />{/if}
    <Knopf text="Umschlag neu aus der Datei" symbol="image" klein laeuft={holtUmschlag} onclick={() => void holeUmschlag()} />
  </div>
  {#if textOffen}<Beschreibungstext {buch} onfertig={() => { textOffen = false; ongeaendert(); }} onabbruch={() => (textOffen = false)} />{/if}
</Karte>

{#if kiOffen}<Kivorschlag {buch} onschliessen={() => (kiOffen = false)} onfertig={() => { kiOffen = false; bestand.geaendert(); ongeaendert(); }} />{/if}
