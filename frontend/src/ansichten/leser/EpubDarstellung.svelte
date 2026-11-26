<script lang="ts">
  import { FARBTHEMEN, GROESSE, ZEILEN } from "../../lib/leser/darstellung";
  import { blattfarbe, type Epubdarstellung } from "../../lib/leser/epub/stile";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import { schale } from "../../lib/stand/schale.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Randregler from "./Randregler.svelte";
  import Schriftwahl from "./Schriftwahl.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  import Themenwahl from "./Themenwahl.svelte";
  let { d, art, onwahl }: { d: Epubdarstellung; art: Leseart; onwahl: (neu: Partial<Epubdarstellung>) => void } = $props();
</script>

<Stufenregler name="Größe" wert={d.groesse} bereich={GROESSE} sprung={10} anzeige="{d.groesse} %" onwahl={(groesse) => onwahl({ groesse })} />
<Stufenregler name="Zeilenabstand" wert={d.zeilen} bereich={ZEILEN} anzeige={d.zeilen.toFixed(1).replace(".", ",")} onwahl={(zeilen) => onwahl({ zeilen })} />
<div class="feld">Schrift<Schriftwahl wert={d.schrift} mitBuch onwahl={(schrift) => onwahl({ schrift })} /></div>
<div class="feld">Papier<Themenwahl fg={d.fg} bg={d.bg} onwahl={(n) => onwahl({ fg: FARBTHEMEN[n].fg, bg: FARBTHEMEN[n].bg })} oneigen={onwahl} /></div>
<div class="feld">
  Durchsichtig
  <div class="reihe">
    <Haekchen text="Rand" an={d.randTransparent} onwahl={(randTransparent) => onwahl({ randTransparent })} />
    <Haekchen text="Seite" an={d.blattTransparent} onwahl={(blattTransparent) => onwahl({ blattTransparent })} />
  </div>
</div>
<!-- Am Telefon steht ohnehin eine Spalte in voller Breite -->
{#if !schale.telefon}
  {#if art === "blaettern"}<div class="feld">Ansicht<Segment name="Ansicht" werte={[["zwei", "Zweiseitig"], ["eins", "Einseitig"]]} wert={d.einseitig ? "eins" : "zwei"} onwahl={(a) => onwahl({ einseitig: a === "eins" })} /></div>{/if}
{/if}
<Randregler />
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
