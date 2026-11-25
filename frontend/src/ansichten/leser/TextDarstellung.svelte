<script module lang="ts">
  export interface Textdarstellung {
    groesse: number;
    schrift: string;
    zeilen: number;
    /** Nummer in BREITEN */
    breite: number;
    fg: string;
    bg: string;
    durchsichtig: boolean;
  }

  export const BREITEN = [
    { name: "Schmal", breite: "37.5rem" }, { name: "Mittel", breite: "50rem" }, { name: "Breit", breite: "68.75rem" }, { name: "Voll", breite: "100%" },
  ];
</script>

<script lang="ts">
  import { FARBTHEMEN, GROESSE, ZEILEN } from "../../lib/leser/darstellung";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Eigenfarbe from "./Eigenfarbe.svelte";
  import Schriftwahl from "./Schriftwahl.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  import Themenwahl from "./Themenwahl.svelte";
  let { d, onwahl }: { d: Textdarstellung; onwahl: (neu: Partial<Textdarstellung>) => void } = $props();
</script>

<Stufenregler name="Größe" wert={d.groesse} bereich={GROESSE} sprung={10} anzeige="{d.groesse} %" onwahl={(groesse) => onwahl({ groesse })} />
<Stufenregler name="Zeilenabstand" wert={d.zeilen} bereich={ZEILEN} anzeige={d.zeilen.toFixed(1).replace(".", ",")} onwahl={(zeilen) => onwahl({ zeilen })} />
<div class="feld">Breite<Segment name="Breite" werte={BREITEN.map((b, n) => [String(n), b.name])} wert={String(d.breite)} onwahl={(n) => onwahl({ breite: Number(n) })} /></div>
<div class="feld">Schrift<Schriftwahl wert={d.schrift} mitBuch onwahl={(schrift) => onwahl({ schrift })} /></div>
<div class="feld">Papier<Themenwahl fg={d.fg} bg={d.bg} onwahl={(n) => onwahl({ fg: FARBTHEMEN[n].fg, bg: FARBTHEMEN[n].bg })} /></div>
<div class="feld">
  Eigene Farben
  <Eigenfarbe name="Papier" wert={d.bg} onwahl={(bg) => onwahl({ bg })} />
  <Eigenfarbe name="Text" wert={d.fg} onwahl={(fg) => onwahl({ fg })} />
</div>
<div class="feld"><Haekchen text="Papier durchsichtig" an={d.durchsichtig} onwahl={(durchsichtig) => onwahl({ durchsichtig })} /></div>
