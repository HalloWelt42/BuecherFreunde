<script lang="ts">
  // Angaben an Ort und Stelle ändern, mit den Werkzeugen für die Angaben über den Feldern (BF-112). Was ein Werkzeug übernimmt,
  // steht messingfarben im Formular; gespeichert wird alles erst mit Speichern, Abbrechen verwirft es. Scheitert das Speichern,
  // bleiben die Eingaben stehen.
  import { beiEsc } from "../../lib/flucht";
  import { arten } from "../../lib/stand/arten.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Angabenfenster from "./Angabenfenster.svelte";
  import { Buchformular, type Textfeld } from "./formular.svelte";
  import Isbnsuche from "./Isbnsuche.svelte";
  import { Angabenwerkzeuge } from "./werkzeuge.svelte";
  import Werkzeugreihe from "./Werkzeugreihe.svelte";

  let { buch, onabbruch, onfertig }: { buch: BuchEinzeln; onabbruch: () => void; onfertig: () => void } = $props();

  // svelte-ignore state_referenced_locally
  const formular = new Buchformular(buch);
  // svelte-ignore state_referenced_locally
  const werkzeuge = new Angabenwerkzeuge(buch, formular);
  const eingabe = formular.eingabe;
  let speichert = $state(false);
  let fehler = $state("");

  // Esc schließt das Bearbeiten nur, wenn kein Fenster der Werkzeuge offen ist (das schließt sich selbst)
  $effect(() => beiEsc(() => werkzeuge.fenster || abbrechen()));
  $effect(() => () => formular.verwerfen());

  let typen = $derived(arten.typWerte(eingabe.typ));
  let gattungen = $derived(arten.gattungWerte(eingabe.gattung));
  let sammlungen = $derived<[string, string][]>([["", "keine"], ...bestand.sammlungen.map((s): [string, string] => [String(s.id), s.name])]);
  const neu = (feld: Textfeld) => formular.eingesetzt.includes(feld);

  function abbrechen() {
    formular.verwerfen();
    onabbruch();
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    fehler = "";
    speichert = true;
    try {
      const fehlt = await formular.speichern();
      if (fehlt) melde.warn(`Gespeichert, Umschlag nicht: ${fehlt}`);
      else melde.gut("Gespeichert");
      bestand.geaendert();
      onfertig();
    } catch (grund) {
      fehler = grund instanceof Error ? grund.message : String(grund);
    } finally {
      speichert = false;
    }
  }
</script>

<form class="buchkopf platte mit-werkzeugen" onsubmit={speichere}>
  <!-- Art und Gattung zeigen sich am Blatt schon vor dem Speichern; ein neuer Umschlag mit "neu" -->
  <div class="kopfblatt">
    {#if formular.umschlag}<span class="umschlag"><img src={formular.umschlag.adresse} alt="" /><span class="format">neu</span></span>
    {:else}<Umschlag buch={{ ...buch, typ: eingabe.typ, gattung: eingabe.gattung }} sofort />{/if}
  </div>
  <Werkzeugreihe {werkzeuge} />
  <div class="felder">
    {#if formular.hinweis}<p class="marke-text info" role="status"><Symbol name="circle-info" /><span>{formular.hinweis}</span></p>{/if}
    <div class="zweifeld">
      <label class="feld ganz" class:eingesetzt={neu("title")}>Titel<input bind:value={eingabe.title} /></label>
      <label class="feld ganz" class:eingesetzt={neu("author")}>Autor<input bind:value={eingabe.author} placeholder="Vorname Nachname, mehrere mit Komma" /></label>
      <label class="feld" class:eingesetzt={neu("publisher")}>Verlag<input bind:value={eingabe.publisher} /></label>
      <label class="feld" class:eingesetzt={neu("year")}>Jahr<input bind:value={eingabe.year} inputmode="numeric" maxlength="4" /></label>
      <label class="feld" class:eingesetzt={neu("language")}>Sprache<input bind:value={eingabe.language} placeholder="de, en" /></label>
      <label class="feld" class:eingesetzt={neu("page_count")}>Seiten<input bind:value={eingabe.page_count} inputmode="numeric" maxlength="5" /></label>
      <div class="feld">Art<Auswahl name="Art" werte={typen} wert={eingabe.typ} onwahl={(w) => (eingabe.typ = w)} /></div>
      <div class="feld">Gattung<Auswahl name="Gattung" werte={gattungen} wert={eingabe.gattung} onwahl={(w) => (eingabe.gattung = w)} /></div>
      <div class="feld">Sammlung<Auswahl name="Sammlung" werte={sammlungen} wert={eingabe.sammlung} onwahl={(w) => (eingabe.sammlung = w)} /></div>
      <label class="feld">Band<input bind:value={eingabe.band} disabled={!eingabe.sammlung} /></label>
      <div class="ganz"><Isbnsuche {werkzeuge} wert={eingabe.isbn} eingesetzt={neu("isbn")} onwert={(w) => (eingabe.isbn = w)} /></div>
      <label class="feld ganz" class:eingesetzt={neu("description")}>Beschreibung<textarea class="eingabe" rows="7" bind:value={eingabe.description}></textarea></label>
    </div>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    <div class="reihe">
      <Knopf text="Speichern" symbol="check" haupt art="submit" laeuft={speichert} />
      <Knopf text="Abbrechen" onclick={abbrechen} />
    </div>
  </div>
</form>

<Angabenfenster {werkzeuge} />

<style>
  .felder {
    display: grid;
    gap: 0.75rem;
    align-content: start;
    min-width: 0;
  }
</style>
