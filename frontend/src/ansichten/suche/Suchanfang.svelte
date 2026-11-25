<script lang="ts">
  // Suche ohne Suchwort: zuletzt Gesuchtes und Weiterlesen
  import { suche } from "../../lib/stand/suche.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Weiterlesen from "../bibliothek/Weiterlesen.svelte";

  const HOECHSTENS = 12;
</script>

<Weiterlesen hoechstens={8} />
{#if suche.verlauf.length}
  <section class="block">
    <div class="titelzeile"><h2>Zuletzt gesucht</h2><span class="schiebt"><Knopf text="Verlauf löschen" symbol="trash" klein frei onclick={() => suche.leere()} /></span></div>
    <div class="platte liste">
      {#each suche.verlauf.slice(0, HOECHSTENS) as wort (wort)}
        <div class="eintrag">
          <button type="button" class="punkt" onclick={() => suche.suche(wort)}><Symbol name="clock-rotate-left" /><span class="name">{wort}</span></button>
          <Knopf text="Aus dem Verlauf nehmen" symbol="xmark" nur klein frei onclick={() => suche.vergiss(wort)} />
        </div>
      {/each}
    </div>
  </section>
{:else}
  <p class="leise">Titel, Autor, ein Satz oder eine Frage: oben eintippen, Treffer zeigen gleich die Stelle.</p>
{/if}

<style>
  .liste {
    padding: 0.25rem;
  }
  .eintrag {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
  }
</style>
