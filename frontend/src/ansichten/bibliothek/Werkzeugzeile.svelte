<script lang="ts">
  import { anzahl, vonGesamt } from "../../lib/format";
  import Schnellfilterchip from "../../lib/schale/Schnellfilterchip.svelte";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { buecher, sortierungen, type Sortierung } from "../../lib/stand/buecher.svelte";
  import { filter } from "../../lib/stand/filter.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Auswahlleiste from "./Auswahlleiste.svelte";
  import Filterfeld from "./Filterfeld.svelte";
  import { regalansicht, regalarten } from "./ansicht.svelte";
  import { regalfilter } from "./schnellfilter";
  import { titelDerFilter } from "./titel";

  let filterOffen = $state(false);
  let filterKnopf = $state<HTMLElement | null>(null);

  const texte = ["txt", "md"];
  let mitText = $derived(texte.every((f) => filter.hat("file_format", f)));
  // Was im Feld "Mehr Filter" gesetzt ist, zählt am Knopf mit
  let weitere = $derived(filter.werte("category").length + (["sammlung", "min_rating", "hat_labels", "hat_highlights"].filter((k) => filter.wert(k)).length) + (filter.hat("file_format", "mobi") ? 1 : 0));

  function schalteText() {
    const rest = filter.werte("file_format").filter((f) => !texte.includes(f));
    filter.setze("file_format", (mitText ? rest : [...rest, ...texte]).join(","));
  }
</script>

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  <h1>{titelDerFilter()}</h1>
  <span class="leise zahl">{!buecher.geladen ? "" : filter.wert("q") ? vonGesamt(buecher.gesamt, buecher.ohneSuche) : anzahl(buecher.gesamt, "Buch", "Bücher")}</span>
  <span class="filter reihe">
    <Schnellfilterchip ziel={regalfilter} />
    <Chip text="PDF" gedrueckt={filter.hat("file_format", "pdf")} onclick={() => filter.schalte("file_format", "pdf")} />
    <Chip text="EPUB" gedrueckt={filter.hat("file_format", "epub")} onclick={() => filter.schalte("file_format", "epub")} />
    <Chip text="Text" titel="TXT und Markdown" gedrueckt={mitText} onclick={schalteText} />
    <Chip text="Favoriten" symbol="heart" gedrueckt={filter.hat("is_favorite", "true")} onclick={() => filter.schalte("is_favorite", "true")} />
    <Chip text="Lesesofa" symbol="couch" gedrueckt={filter.hat("is_to_read", "true")} onclick={() => filter.schalte("is_to_read", "true")} />
    {#if filter.aktiv}<Chip text="Filter aufheben" symbol="xmark" onclick={() => filter.leere()} />{/if}
  </span>
  <span class="mehrfilter" bind:this={filterKnopf}><Chip text="Mehr" symbol="sliders" zahl={weitere || undefined} gedrueckt={filterOffen || weitere > 0} titel="Regale, Sammlung, Format, Bewertung, Etiketten" onclick={() => (filterOffen = !filterOffen)} /></span>
  <span class="reihe schiebt">
    <span class="sortierung reihe">
      <Auswahl name="Sortierung" klein werte={sortierungen.map(([w, t]) => [w, t])} wert={buecher.sortierung} onwahl={(w) => w !== buecher.sortierung && buecher.sortiere(w as Sortierung)} />
      <Knopf text={buecher.richtung === "asc" ? "Aufsteigend, umdrehen" : "Absteigend, umdrehen"} symbol={buecher.richtung === "asc" ? "arrow-up-short-wide" : "arrow-down-wide-short"} nur klein onclick={() => buecher.dreheRichtung()} />
    </span>
    <Segment name="Ansicht" nurSymbole werte={regalarten} wert={regalansicht.art} onwahl={(w) => (regalansicht.art = w)} />
    <span class="bearbeiten"><Knopf text="Bearbeiten" symbol="pen" klein gedrueckt={auswahl.bearbeiten} onclick={() => auswahl.modus(!auswahl.bearbeiten)} /></span>
  </span>
  {#if auswahl.bearbeiten}<Auswahlleiste />{/if}
</div>

{#if filterOffen}
  <Menue anker={filterKnopf} name="Filter" breite="23rem" onschliessen={() => (filterOffen = false)}><Filterfeld /></Menue>
{/if}
