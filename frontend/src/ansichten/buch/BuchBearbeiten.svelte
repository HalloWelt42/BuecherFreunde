<script lang="ts">
  // Angaben an Ort und Stelle ändern; scheitert das Speichern, bleiben die Eingaben stehen
  import { untrack } from "svelte";
  import { aktualisiereBuch } from "../../lib/api/books";
  import { buchAusSammlung, buchZuordnen } from "../../lib/api/collections";
  import { beiEsc } from "../../lib/flucht";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Isbnsuche from "./Isbnsuche.svelte";
  import { TYPEN } from "./typen";

  let { buch, onabbruch, onfertig }: { buch: BuchEinzeln; onabbruch: () => void; onfertig: () => void } = $props();

  let eingabe = $state(
    untrack(() => ({
      title: buch.title, author: buch.author, isbn: buch.isbn, year: buch.year ? String(buch.year) : "", publisher: buch.publisher, language: buch.language,
      page_count: buch.page_count ? String(buch.page_count) : "", typ: buch.typ, sammlung: buch.sammlung_id ? String(buch.sammlung_id) : "", band: buch.band_nummer, description: buch.description,
    })),
  );
  let speichert = $state(false);
  let hinweis = $state("");

  $effect(() => beiEsc(() => onabbruch()));

  const typen: [string, string][] = [["", "Buch"], ...Object.entries(TYPEN)];
  let sammlungen = $derived<[string, string][]>([["", "keine"], ...bestand.sammlungen.map((s): [string, string] => [String(s.id), s.name])]);

  function alsZahl(text: string, feld: string): number | null {
    if (!text.trim()) return null;
    if (!/^\d{1,5}$/.test(text.trim())) throw new Error(`${feld} ist keine Zahl`);
    return Number(text.trim());
  }

  function aenderungen(): Record<string, unknown> {
    const daten: Record<string, unknown> = {};
    for (const k of ["title", "author", "isbn", "publisher", "language", "typ", "description"] as const) {
      if (eingabe[k] !== (buch[k] ?? "")) daten[k] = eingabe[k];
    }
    if (!eingabe.title.trim()) throw new Error("Der Titel fehlt");
    const jahr = alsZahl(eingabe.year, "Das Jahr");
    if (jahr !== buch.year) daten.year = jahr;
    const seiten = alsZahl(eingabe.page_count, "Die Seitenzahl") ?? 0;
    if (seiten !== buch.page_count) daten.page_count = seiten;
    return daten;
  }

  async function speichereSammlung() {
    const neu = eingabe.sammlung ? Number(eingabe.sammlung) : null;
    if (neu === buch.sammlung_id && eingabe.band === buch.band_nummer) return;
    if (neu) await buchZuordnen(neu, buch.id, eingabe.band);
    else if (buch.sammlung_id) await buchAusSammlung(buch.sammlung_id, buch.id);
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    hinweis = "";
    speichert = true;
    try {
      const daten = aenderungen();
      await speichereSammlung();
      if (Object.keys(daten).length) await aktualisiereBuch(buch.id, daten);
      melde.gut("Gespeichert");
      bestand.geaendert();
      onfertig();
    } catch (grund) {
      hinweis = grund instanceof Error ? grund.message : String(grund);
    } finally {
      speichert = false;
    }
  }
</script>

<form class="buchkopf platte" onsubmit={speichere}>
  <div><Umschlag {buch} sofort /></div>
  <div class="felder">
    <div class="zweifeld">
      <label class="feld ganz">Titel<input bind:value={eingabe.title} /></label>
      <label class="feld ganz">Autor<input bind:value={eingabe.author} placeholder="Vorname Nachname, mehrere mit Komma" /></label>
      <label class="feld">Verlag<input bind:value={eingabe.publisher} /></label>
      <label class="feld">Jahr<input bind:value={eingabe.year} inputmode="numeric" maxlength="4" /></label>
      <label class="feld">Sprache<input bind:value={eingabe.language} placeholder="de, en" /></label>
      <label class="feld">Seiten<input bind:value={eingabe.page_count} inputmode="numeric" maxlength="5" /></label>
      <div class="feld">Typ<Auswahl name="Typ" werte={typen} wert={eingabe.typ} onwahl={(w) => (eingabe.typ = w)} /></div>
      <div class="feld">Sammlung<Auswahl name="Sammlung" werte={sammlungen} wert={eingabe.sammlung} onwahl={(w) => (eingabe.sammlung = w)} /></div>
      <label class="feld">Band<input bind:value={eingabe.band} disabled={!eingabe.sammlung} /></label>
      <div class="ganz"><Isbnsuche {buch} wert={eingabe.isbn} onwert={(w) => (eingabe.isbn = w)} /></div>
      <label class="feld ganz">Beschreibung<textarea class="eingabe" rows="7" bind:value={eingabe.description}></textarea></label>
    </div>
    {#if hinweis}<p class="marke-text schlecht" role="alert">{hinweis}</p>{/if}
    <div class="reihe">
      <Knopf text="Speichern" symbol="check" haupt art="submit" laeuft={speichert} />
      <Knopf text="Abbrechen" onclick={onabbruch} />
    </div>
  </div>
</form>

<style>
  .felder {
    display: grid;
    gap: 0.75rem;
    align-content: start;
    min-width: 0;
  }
</style>
