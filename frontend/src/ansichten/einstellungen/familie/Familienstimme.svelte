<script lang="ts">
  // Stimme der Familie (BF-78, Entwurf kinder-6 Abschnitt 5): spricht "Wer liest?" und die Namen und gilt für jedes Kind ohne
  // eigene Wahl. Unter der Liste der Profile; ändern darf sie, wer Profile verwaltet, vorhören auch, wer freigibt.
  import { setzeFamilienstimme } from "../../../lib/api/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Stimmwahl from "./Stimmwahl.svelte";

  async function waehle(stimme: string) {
    try {
      await setzeFamilienstimme(stimme);
      await familie.laden();
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
    }
  }
</script>

<div class="elternzeile familienstimme">
  <span>Stimme der Familie<small>spricht 'Wer liest?' und die Namen, Vorgabe für alle Kinder</small></span>
  <Stimmwahl stimme={familie.stimme} name="Stimme der Familie" nurSymbol gesperrt={!ich.darf("profile")} onwahl={waehle} />
</div>

<style>
  /* In der schmalen Liste: reicht der Platz nicht, rücken Probe und Stimme unter den Text */
  .familienstimme {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin-top: 0.625rem;
    padding: 0.5rem 0.5rem 0;
    border-top: 1px solid var(--linie);
  }
  .familienstimme > span:first-child {
    flex: 1 1 6rem;
  }
  .familienstimme > :global(.stimmtasten) {
    margin-left: auto;
  }
</style>
