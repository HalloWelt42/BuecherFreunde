<script lang="ts">
  // Vorschlag aus dem Lexikon neben den Angaben der Bibliothek; nichts ändert sich vor dem Übernehmen
  import { autorenFotoUrl, uebernehmAutorenDaten, type Anreicherung, type Autoreneinzeln } from "../../lib/api/authors";
  import { navigate } from "../../lib/router.svelte.js";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Vergleichstabelle, { type Vergleichszeile } from "../../lib/teile/Vergleichstabelle.svelte";
  import Konfidenz from "./Konfidenz.svelte";
  import { imBestand, uebernahmefelder, vergleichszeilen } from "./angaben";

  let { autor, antwort, onfertig, onverwerfen }: { autor: Autoreneinzeln; antwort: Anreicherung; onfertig: () => void; onverwerfen: () => void } = $props();

  // svelte-ignore state_referenced_locally
  let zeilen = $state<Vergleichszeile[]>(vergleichszeilen(autor, antwort, autorenFotoUrl(autor.id, "thumb")));
  let laeuft = $state(false);
  let gescheitert = $state("");

  let vorschlag = $derived(antwort.vorschlag ?? {});
  let gewaehlt = $derived(zeilen.filter((z) => z.gewaehlt && !z.gleich).length);
  let werke = $derived(vorschlag.werke ?? []);
  let buecher = $derived(antwort.buecher_im_system ?? []);
  let vorhanden = $derived(werke.filter((w) => imBestand(w.titel, buecher)).length);

  function schalte(schluessel: string, an: boolean) {
    zeilen = zeilen.map((z) => (z.schluessel === schluessel ? { ...z, gewaehlt: an } : z));
  }

  async function uebernimm() {
    laeuft = true;
    gescheitert = "";
    try {
      const e = await uebernehmAutorenDaten(autor.id, uebernahmefelder(vorschlag, zeilen));
      if (e.zusammengefuehrt && e.ziel_autor_id) {
        melde.info(`Diesen Eintrag hat schon ${e.ziel_autor_name}. Beide Autoren sind jetzt einer.`);
        bestand.geaendert();
        navigate(`/author/${e.ziel_autor_id}`, true);
        return;
      }
      melde.gut("Übernommen");
      onfertig();
    } catch (grund) {
      gescheitert = grund instanceof Error ? grund.message : String(grund);
    } finally {
      laeuft = false;
    }
  }

  async function verwirf() {
    const ja = await frage({ titel: "Vorschlag verwerfen?", folgen: ["Die gefundenen Angaben verschwinden. Der Abgleich lässt sich jederzeit neu starten."], ja: "Verwerfen", symbol: "xmark" });
    if (ja) onverwerfen();
  }
</script>

<Karte titel="Angaben vergleichen" symbol="code-compare" breit>
  {#snippet neben()}{#if vorschlag.konfidenz}<Konfidenz stufe={vorschlag.konfidenz} punkte={vorschlag.score} />{/if}{/snippet}
  <p class="leise">Vorschlag von Wikipedia und Wikidata. Nichts ändert sich vor dem Übernehmen.</p>
  <Vergleichstabelle {zeilen} gesperrt={laeuft} onwahl={schalte} />
  {#if werke.length}
    <details>
      <summary>Werkliste, {werke.length} Titel, davon {vorhanden} in der Bibliothek</summary>
      <ul class="werkliste">
        {#each werke as w, n (n)}<li><span>{w.titel}</span>{#if imBestand(w.titel, buecher)}<span class="marke-text gut"><Symbol name="check" />im Bestand</span>{/if}</li>{/each}
      </ul>
    </details>
  {/if}
  {#if gescheitert}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />Nicht übernommen: {gescheitert}</p>{/if}
  <div class="reihe">
    <Knopf text="{gewaehlt} {gewaehlt === 1 ? 'Feld' : 'Felder'} übernehmen" symbol="check" haupt klein gesperrt={!gewaehlt} {laeuft} onclick={() => void uebernimm()} />
    <Knopf text="Verwerfen" symbol="xmark" klein gesperrt={laeuft} onclick={() => void verwirf()} />
  </div>
</Karte>

<style>
  summary {
    cursor: pointer;
    min-height: 1.875rem;
    padding: 0.25rem 0;
  }
</style>
