<script module lang="ts">
  export interface Textdarstellung {
    groesse: number;
    schrift: string;
    zeilen: number;
    fg: string;
    bg: string;
    durchsichtig: boolean;
  }
</script>

<script lang="ts">
  import { FARBTHEMEN, GROESSE, ZEILEN } from "../../lib/leser/darstellung";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Randregler from "./Randregler.svelte";
  import Schriftwahl from "./Schriftwahl.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  import Themenwahl from "./Themenwahl.svelte";
  let { d, onwahl }: { d: Textdarstellung; onwahl: (neu: Partial<Textdarstellung>) => void } = $props();
</script>

<Stufenregler name="Größe" wert={d.groesse} bereich={GROESSE} sprung={10} anzeige="{d.groesse} %" onwahl={(groesse) => onwahl({ groesse })} />
<Stufenregler name="Zeilenabstand" wert={d.zeilen} bereich={ZEILEN} anzeige={d.zeilen.toFixed(1).replace(".", ",")} onwahl={(zeilen) => onwahl({ zeilen })} />
<Randregler />
<div class="feld">Schrift<Schriftwahl wert={d.schrift} mitBuch onwahl={(schrift) => onwahl({ schrift })} /></div>
<div class="feld">Papier<Themenwahl fg={d.fg} bg={d.bg} onwahl={(n) => onwahl({ fg: FARBTHEMEN[n].fg, bg: FARBTHEMEN[n].bg })} oneigen={onwahl} /></div>
<div class="feld"><Haekchen text="Papier durchsichtig" an={d.durchsichtig} onwahl={(durchsichtig) => onwahl({ durchsichtig })} /></div>
