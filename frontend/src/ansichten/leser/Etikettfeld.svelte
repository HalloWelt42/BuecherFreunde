<script lang="ts">
  // Neues Etikett an der Stelle, an der man gerade liest
  import { VORGABE_ETIKETT } from "../../lib/leser/farben";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Farbreihe from "./Farbreihe.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  let offen = $state(false);
  let name = $state("");
  let notiz = $state("");
  let farbe = $state(VORGABE_ETIKETT);

  // "Etikett hier" aus dem Kontextmenü öffnet die Eingabe gleich
  $effect(() => {
    if (!sitzung.etikettWunsch) return;
    offen = true;
    sitzung.etikettWunsch = false;
  });

  async function lege(e: SubmitEvent) {
    e.preventDefault();
    if (!(await sitzung.neuesEtikett(name, notiz, farbe))) return;
    [name, notiz, offen] = ["", "", false];
  }
</script>

{#if offen}
  <form onsubmit={lege}>
    <input class="eingabe" placeholder="Name" aria-label="Name des Etiketts" maxlength="50" bind:value={name} />
    <textarea class="eingabe" rows="2" placeholder="Notiz" aria-label="Notiz zum Etikett" bind:value={notiz}></textarea>
    <Farbreihe name="Farbe des Etiketts" wert={farbe} onwahl={(f) => (farbe = f)} />
    <div class="reihe"><Knopf text="Etikett setzen" symbol="tag" klein art="submit" /><Knopf text="Abbrechen" klein frei onclick={() => (offen = false)} /></div>
  </form>
{:else}
  <div class="reihe"><Knopf text="Etikett an dieser Stelle" symbol="tag" klein onclick={() => (offen = true)} /></div>
{/if}

<style>
  form {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: minmax(0, 1fr);
  }
</style>
