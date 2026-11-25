<script lang="ts">
  import { BREITE_EINS, BREITE_ZWEI, FARBTHEMEN, GROESSE, ZEILEN } from "../../lib/leser/darstellung";
  import { blattfarbe, einspaltig, type Epubdarstellung } from "../../lib/leser/epub/stile";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Eigenfarbe from "./Eigenfarbe.svelte";
  import Schriftwahl from "./Schriftwahl.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  import Themenwahl from "./Themenwahl.svelte";
  let { d, art, onwahl }: { d: Epubdarstellung; art: Leseart; onwahl: (neu: Partial<Epubdarstellung>) => void } = $props();
</script>

<Stufenregler name="Größe" wert={d.groesse} bereich={GROESSE} sprung={10} anzeige="{d.groesse} %" onwahl={(groesse) => onwahl({ groesse })} />
<Stufenregler name="Zeilenabstand" wert={d.zeilen} bereich={ZEILEN} anzeige={d.zeilen.toFixed(1).replace(".", ",")} onwahl={(zeilen) => onwahl({ zeilen })} />
<div class="feld">Schrift<Schriftwahl wert={d.schrift} mitBuch onwahl={(schrift) => onwahl({ schrift })} /></div>
<div class="feld">Papier<Themenwahl fg={d.fg} bg={d.bg} onwahl={(n) => onwahl({ fg: FARBTHEMEN[n].fg, bg: FARBTHEMEN[n].bg })} /></div>
<div class="feld">
  Eigene Farben
  <Eigenfarbe name="Papier" wert={d.bg} onwahl={(bg) => onwahl({ bg })} />
  <Eigenfarbe name="Text" wert={d.fg} onwahl={(fg) => onwahl({ fg })} />
</div>
<div class="feld">
  Durchsichtig
  <Haekchen text="Rand" an={d.randTransparent} onwahl={(randTransparent) => onwahl({ randTransparent })} />
  <Haekchen text="Seite" an={d.blattTransparent} onwahl={(blattTransparent) => onwahl({ blattTransparent })} />
</div>
{#if art === "blaettern"}<div class="feld">Ansicht<Segment name="Ansicht" werte={[["zwei", "Zweiseitig"], ["eins", "Einseitig"]]} wert={d.einseitig ? "eins" : "zwei"} onwahl={(a) => onwahl({ einseitig: a === "eins" })} /></div>{/if}
{#if einspaltig(d, art)}
  <Stufenregler name="Breite" wert={d.breiteEins} bereich={BREITE_EINS} anzeige="{d.breiteEins} px" onwahl={(breiteEins) => onwahl({ breiteEins })} />
{:else}
  <Stufenregler name="Breite" wert={d.breiteZwei} bereich={BREITE_ZWEI} anzeige="{d.breiteZwei} px" onwahl={(breiteZwei) => onwahl({ breiteZwei })} />
{/if}
<div class="feld">
  Vorschau
  <p class="probe" style:background={blattfarbe(d)} style:color={d.fg} style:font-size="{d.groesse / 100}rem" style:line-height={d.zeilen} style:font-family={d.schrift || undefined}>Die Sonne ging unter und tauchte die Stadt in ein warmes, goldenes Licht.</p>
</div>

<style>
  .probe {
    width: 100%;
    padding: 0.625rem;
    border-radius: 3px;
    box-shadow: inset 0 0 0 1px var(--linie);
    overflow-wrap: anywhere;
  }
</style>
