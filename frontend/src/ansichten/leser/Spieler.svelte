<script lang="ts">
  // Tasten des Vorlesens: Abschnitt und Satz zurück, Pause oder weiter, Satz und Abschnitt vor, Stopp
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { art = "Seite" }: { art?: string } = $props();
</script>

<div class="spieler" role="group" aria-label="Vorlesen steuern">
  <Knopf text="{art} zurück" symbol="backward-step" nur klein frei onclick={() => vorlesen.einheitZurueck()} />
  <Knopf text="Satz zurück" symbol="backward" nur klein frei onclick={() => vorlesen.satzZurueck()} />
  <!-- Holt die Vertonung noch den Ton, dreht das Zeichen; Pause geht trotzdem (BF-121): angehalten bleibt es auch, wenn der Ton ankommt -->
  <Knopf klasse="haupt-taste" text={vorlesen.pausiert ? "Weiter" : "Pause"} symbol={vorlesen.pausiert ? "play" : "pause"} nur klein dreht={vorlesen.wartet && !vorlesen.pausiert} onclick={() => vorlesen.pauseOderWeiter()} />
  <Knopf text="Satz vor" symbol="forward" nur klein frei onclick={() => vorlesen.satzVor()} />
  <Knopf text="{art} vor" symbol="forward-step" nur klein frei gesperrt={!vorlesen.kannVor} onclick={() => vorlesen.einheitVor()} />
  <Knopf text="Stopp" symbol="stop" nur klein frei onclick={() => vorlesen.halt()} />
</div>

<style>
  .spieler {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 0.25rem;
    width: 100%;
  }
  .spieler :global(.knopf) {
    width: 100%;
  }
</style>
