<script lang="ts">
  import { ladeAnweisungen, type Anweisung } from "../../lib/api/ai";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Anweisungsformular from "./Anweisungsformular.svelte";

  let liste = $state<Anweisung[] | null>(null);
  let fehler = $state("");
  let offen = $state<Anweisung | null>(null);

  async function lade() {
    fehler = "";
    try {
      liste = await ladeAnweisungen();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }
  $effect(() => void lade());

  const dezimal = (n: number) => String(n).replace(".", ",");
</script>

{#if fehler}
  <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
{:else if !liste}
  <Zustand art="laedt" text="Wird geladen" />
{:else}
  {#each liste as a (a.id)}
    <div class="stelle zeile-stand eins-knopf">
      <div class="anweisung">
        <b>{a.name}</b>{#if !a.aktiv} <span class="marke-text warn">aus</span>{/if}<br />
        <span class="leise">{a.beschreibung || a.schluessel}</span><br />
        <span class="leise zahl">Temperatur {dezimal(a.temperatur)}, höchstens {a.max_tokens} Token</span>
        <p class="anweisungstext">{a.system_prompt}</p>
      </div>
      <Knopf text="Bearbeiten" symbol="pen" nur klein frei onclick={() => (offen = a)} />
    </div>
  {:else}<p class="leise">Noch keine Anweisung vorhanden.</p>{/each}
{/if}

{#if offen}<Anweisungsformular anweisung={offen} onschliessen={() => (offen = null)} ongespeichert={() => void lade()} />{/if}
