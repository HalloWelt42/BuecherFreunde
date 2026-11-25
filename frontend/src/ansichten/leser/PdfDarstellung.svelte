<script lang="ts">
  import { GROESSE, PAPIERE, vorgabeThema, ZEILEN, type Papier } from "../../lib/leser/darstellung";
  import { ANSICHTEN, type Ansicht } from "../../lib/leser/pdf/zoom";
  import { textansicht } from "../../lib/leser/textansicht.svelte";
  import { darstellung } from "../../lib/stand/darstellung.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Schriftwahl from "./Schriftwahl.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  import Themenwahl from "./Themenwahl.svelte";

  interface Eigenschaften {
    ansicht: Ansicht;
    nurText: boolean;
    mass: number;
    papier: Papier;
    stufen: number[];
    onansicht: (a: Ansicht | "text") => void;
    onzoom: (richtung: 1 | -1) => void;
    onoriginalgroesse: () => void;
    onpapier: (p: Papier) => void;
  }
  let { ansicht, nurText, mass, papier, stufen, onansicht, onzoom, onoriginalgroesse, onpapier }: Eigenschaften = $props();
  let thema = $derived(textansicht.thema(vorgabeThema(darstellung.dunkel)));
</script>

{#if nurText}
  <Stufenregler name="Größe" wert={textansicht.groesse} bereich={{ ...GROESSE, vorgabe: 110 }} anzeige="{textansicht.groesse} %" onwahl={(w) => (textansicht.groesse = w)} />
  <Stufenregler name="Zeilenabstand" wert={textansicht.zeilen} bereich={ZEILEN} anzeige={textansicht.zeilen.toFixed(1).replace(".", ",")} onwahl={(w) => (textansicht.zeilen = w)} />
  <div class="feld">Schrift<Schriftwahl wert={textansicht.familie} onwahl={(f) => (textansicht.familie = f)} /></div>
  <div class="feld">Farbe<Themenwahl fg={thema.fg} bg={thema.bg} onwahl={(n) => textansicht.setzeThema(n)} /></div>
{:else}
  <div class="feld">
    Größe
    <div class="reihe">
      <Knopf text="Kleiner" symbol="minus" nur klein gesperrt={mass <= stufen[0] + 0.005} onclick={() => onzoom(-1)} />
      <Knopf text="{Math.round(mass * 100)} %" klein titel="Auf 100 % setzen" onclick={onoriginalgroesse} />
      <Knopf text="Größer" symbol="plus" nur klein gesperrt={mass >= stufen[stufen.length - 1] - 0.005} onclick={() => onzoom(1)} />
    </div>
  </div>
  <div class="feld">Papier<div class="reihe">{#each PAPIERE as [w, t] (w)}<Chip text={t} gedrueckt={papier === w} onclick={() => onpapier(w)} />{/each}</div></div>
{/if}
<div class="feld">
  Ansicht
  <div class="reihe">{#each ANSICHTEN as [w, t] (w)}<Chip text={t} gedrueckt={nurText ? w === "text" : w === ansicht} onclick={() => onansicht(w)} />{/each}</div>
</div>
