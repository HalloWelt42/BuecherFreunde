<script lang="ts">
  // Feld "Fokus und Hilfen" am Rechner: Fokus mit Art und Stärke, Ruhe, von selbst lesen
  import { BEREICHE, FOKUSFARBEN, lesehilfen, type Fokusart, type Huelle } from "../../lib/leser/lesehilfen.svelte";
  import { selbstlauf } from "../../lib/leser/selbstlauf.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  let f = $derived(lesehilfen.fokus);
  let arten = $derived<[Fokusart, string, string][]>([["fenster", "Fenster", "vector-square"], ["lineal", "Lineal", "ruler-horizontal"], ...(sitzung.hilfe?.mitAbsaetzen ? [["absatz", "Absatz", "paragraph"] as [Fokusart, string, string]] : [])]);
  const HUELLEN: [Huelle, string][] = [["dunkel", "Dunkel"], ["milchig", "Milchig"]];
  const prozent = (w: number) => `${Math.round(w)} %`;

  function selbst() {
    if (selbstlauf.an) selbstlauf.halt();
    else if (sitzung.hilfe) selbstlauf.starte(sitzung.hilfe, lesehilfen.tempo);
  }
</script>

<h2>Fokus und Hilfen</h2>
<div class="feld">
  Fokus
  <Haekchen text="Fokus zeigen" an={f.an} onwahl={(an) => lesehilfen.setzeFokus({ an })} />
  <Segment name="Art des Fokus" werte={arten} wert={f.art === "absatz" && !sitzung.hilfe?.mitAbsaetzen ? "lineal" : f.art} onwahl={(art) => lesehilfen.setzeFokus({ art, an: true })} />
  {#if f.art === "fenster"}<p class="klein leise">Am Rand ziehen verschiebt, Kanten und Ecken ändern die Größe, Doppelklick stellt zurück.</p>{/if}
  {#if f.art === "lineal"}<Haekchen text="Folgt der Maus" an={f.folgt} onwahl={(folgt) => lesehilfen.setzeFokus({ folgt })} />{/if}
  {#if f.art === "lineal" && !f.folgt}<p class="klein leise">Steht fest: am Rand ziehen oder Pfeiltasten.</p>{/if}
</div>
{#if f.art === "lineal"}<Stufenregler name="Zeilen" wert={f.zeilen} bereich={BEREICHE.zeilen} anzeige={String(f.zeilen)} onwahl={(zeilen) => lesehilfen.setzeFokus({ zeilen })} />{/if}
<div class="feld">Außen<Segment name="Außen" werte={HUELLEN} wert={f.huelle} onwahl={(huelle) => lesehilfen.setzeFokus({ huelle })} /></div>
<Stufenregler name="Stärke" wert={Math.round(f.staerke * 100)} bereich={BEREICHE.staerke} anzeige={prozent(f.staerke * 100)} onwahl={(w) => lesehilfen.setzeFokus({ staerke: w / 100 })} />
<Stufenregler name="Übergang" wert={f.verlauf} bereich={BEREICHE.verlauf} anzeige="{f.verlauf} px" onwahl={(verlauf) => lesehilfen.setzeFokus({ verlauf })} />
{#if f.huelle === "dunkel"}
  <div class="feld">
    Farbe
    <div class="farbreihe" role="group" aria-label="Farbe außen">
      {#each FOKUSFARBEN as [farbe, name] (farbe)}<button type="button" style:background={farbe} aria-label={name} title={name} aria-pressed={f.farbe === farbe} onclick={() => lesehilfen.setzeFokus({ farbe })}></button>{/each}
    </div>
  </div>
{/if}
<div class="feld trenner">
  Ruhe
  <Haekchen text="Leisten und Zeiger blenden sich aus, solange man liest" an={lesehilfen.ruhe} onwahl={(an) => (lesehilfen.ruhe = an)} />
</div>
<div class="feld">
  Von selbst
  <Knopf text={selbstlauf.an ? "Anhalten" : "Von selbst lesen"} symbol={selbstlauf.an ? "stop" : "play"} klein gesperrt={!sitzung.hilfe} onclick={selbst} />
</div>
<Stufenregler name="Tempo" wert={lesehilfen.tempo} bereich={BEREICHE.tempo} anzeige="{lesehilfen.tempo} Zeilen je Minute" onwahl={(t) => { lesehilfen.tempo = t; selbstlauf.tempo = t; }} />
<Knopf text="Tastenkürzel" symbol="keyboard" klein frei onclick={() => (sitzung.feld = "tasten")} />

<style>
  .trenner {
    border-top: 1px solid var(--linie);
    padding-top: 0.75rem;
  }
</style>
