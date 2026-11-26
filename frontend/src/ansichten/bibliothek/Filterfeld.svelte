<script lang="ts">
  // Alle Filter, die nicht in der Leiste stehen: Regale mit Suche, Sammlung, Formate, ISBN, Bewertung, Etiketten
  import { eingrenzen } from "../../lib/eingrenzen";
  import { zahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { filter } from "../../lib/stand/filter.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  const formate: [string, string][] = [["pdf", "PDF"], ["epub", "EPUB"], ["mobi", "MOBI"], ["txt", "TXT"], ["md", "Markdown"]];
  const bewertungen: [string, string][] = [["5", "5"], ["4", "ab 4"], ["3", "ab 3"], ["2", "ab 2"], ["1", "ab 1"]];
  const HOECHSTENS = 50;

  let suche = $state("");
  let passend = $derived(bestand.regale.filter((r) => r.name.toLowerCase().includes(suche.trim().toLowerCase())));
  // Kategorien des Katalogs stehen im selben Filter; hier geht es nur um die Regale (BF-69)
  let gewaehlteRegale = $derived(filter.werte("category").filter((id) => bestand.regal(id)));
  // Sammlungen als Chips; bei vielen mit Suche und höchstens so vielen
  const SAMMLUNGEN_HOECHSTENS = 24;
  let sammlungswort = $state("");
  let sammlungen = $derived(eingrenzen(bestand.sammlungen, (s) => s.name, sammlungswort, (s) => filter.hat("sammlung", String(s.id)), SAMMLUNGEN_HOECHSTENS));
</script>

<h2>Filter</h2>
<div class="gruppen">
  <section>
    <div class="reihe"><h3>Regale</h3>{#if gewaehlteRegale.length}<span class="schiebt"><Knopf text="Auswahl aufheben" symbol="xmark" klein frei onclick={() => filter.setzeWerte("category", filter.werte("category").filter((id) => !bestand.regal(id)))} /></span>{/if}</div>
    <input class="eingabe" type="search" placeholder="Regal suchen" aria-label="Regal suchen" bind:value={suche} />
    <div class="regalliste">
      {#each passend.slice(0, HOECHSTENS) as r (r.id)}
        <Haekchen an={gewaehlteRegale.includes(String(r.id))} onwahl={() => filter.schalte("category", String(r.id))}>{r.name} <span class="leise zahl">{zahl(r.buch_anzahl)}</span></Haekchen>
      {:else}<p class="leise">Kein Regal heißt so.</p>{/each}
      {#if passend.length > HOECHSTENS}<p class="leise">Noch {passend.length - HOECHSTENS} weitere, Suche verfeinern.</p>{/if}
    </div>
  </section>
  {#if bestand.sammlungen.length}
    <section>
      <h3>Sammlung</h3>
      {#if sammlungen.mitSuche}<input class="eingabe" type="search" placeholder="Sammlung suchen" aria-label="Sammlung suchen" bind:value={sammlungswort} />{/if}
      <div class="reihe">{#each sammlungen.gezeigt as s (s.id)}<Chip text={s.name} farbe={s.color} zahl={zahl(s.buch_anzahl)} gedrueckt={filter.hat("sammlung", String(s.id))} onclick={() => filter.schalte("sammlung", String(s.id))} />{:else}<p class="leise">Keine Sammlung heißt so.</p>{/each}</div>
      {#if sammlungen.weitere}<p class="leise">Noch {sammlungen.weitere} weitere, Suche verfeinern.</p>{/if}
    </section>
  {/if}
  <section>
    <h3>Format</h3>
    <div class="reihe">{#each formate as [w, t] (w)}<Chip text={t} gedrueckt={filter.hat("file_format", w)} onclick={() => filter.schalte("file_format", w)} />{/each}</div>
  </section>
  <section>
    <h3>ISBN</h3>
    <div class="reihe">
      <Chip text="Mit ISBN" symbol="barcode" gedrueckt={filter.hat("hat_isbn", "true")} onclick={() => filter.schalte("hat_isbn", "true")} />
      <Chip text="Ohne ISBN" symbol="file-lines" gedrueckt={filter.hat("hat_isbn", "false")} onclick={() => filter.schalte("hat_isbn", "false")} />
    </div>
  </section>
  <section>
    <h3>Bewertung</h3>
    <div class="reihe">{#each bewertungen as [w, t] (w)}<Chip text={t} symbol="star" gedrueckt={filter.hat("min_rating", w)} onclick={() => filter.schalte("min_rating", w)} />{/each}</div>
  </section>
  <section>
    <h3>Markiert und benannt</h3>
    <div class="reihe">
      <Chip text="Mit Markierungen" symbol="highlighter" gedrueckt={filter.hat("hat_highlights", "true")} onclick={() => filter.schalte("hat_highlights", "true")} />
      <Chip text="Mit Etiketten" symbol="tag" gedrueckt={filter.hat("hat_labels", "true")} onclick={() => filter.schalte("hat_labels", "true")} />
    </div>
  </section>
</div>

<style>
  .gruppen,
  section {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .gruppen {
    gap: 0.875rem;
  }
  h3 {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--tinte-2);
  }
  .regalliste {
    display: grid;
    max-height: 13rem;
    overflow: auto;
  }
</style>
