<script lang="ts">
  // Regale von der KI vorschlagen lassen, wählen, übernehmen; beim Bearbeiten mit Speichern, auf der Buchseite gleich (ziel.ts)
  import { kategorisiere } from "../../lib/api/ai";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Angabenziel } from "./ziel";

  let { buchId, ziel, onschliessen }: { buchId: number; ziel: Angabenziel; onschliessen: () => void } = $props();

  interface Vorschlag {
    name: string;
    sicher: number;
    an: boolean;
  }
  let vorschlaege = $state<Vorschlag[]>([]);
  let laedt = $state(true);
  let speichert = $state(false);
  let fehler = $state("");
  let gewaehlt = $derived(vorschlaege.filter((v) => v.an));

  async function hole() {
    laedt = true;
    fehler = "";
    try {
      const a = await kategorisiere(buchId);
      vorschlaege = (a.vorschlaege ?? []).map((v: { kategorie?: string; category?: string; konfidenz?: number; confidence?: number }) => ({ name: v.kategorie ?? v.category ?? "", sicher: v.konfidenz ?? v.confidence ?? 0, an: true })).filter((v: Vorschlag) => v.name);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      laedt = false;
    }
  }

  $effect(() => void hole());

  async function uebernimm() {
    speichert = true;
    try {
      await ziel.regale(gewaehlt.map((v) => v.name));
      onschliessen();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      speichert = false;
    }
  }
</script>

<Fenster titel="Vorschlag der KI" breite="28rem" {onschliessen}>
  {#if laedt}
    <Zustand art="laedt" text="Das Buch wird gelesen und eingeordnet" />
  {:else if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void hole()} />
  {:else if !vorschlaege.length}
    <Zustand text="Die KI hat kein passendes Regal gefunden." onerneut={() => void hole()} />
  {:else}
    <div class="liste">
      {#each vorschlaege as v (v.name)}
        <span class="reihe"><Haekchen text={v.name} an={v.an} onwahl={(an) => (v.an = an)} /><span class="schiebt marke-text {v.sicher >= 0.8 ? 'gut' : v.sicher >= 0.5 ? 'warn' : 'schlecht'}">{Math.round(v.sicher * 100)} %</span></span>
      {/each}
    </div>
  {/if}
  {#snippet fuss()}
    <span class="schiebt reihe"><Knopf text="Abbrechen" onclick={onschliessen} /><Knopf text="Übernehmen" symbol="check" haupt gesperrt={!gewaehlt.length || laedt} laeuft={speichert} onclick={() => void uebernimm()} /></span>
  {/snippet}
</Fenster>

<style>
  .liste {
    display: grid;
    gap: 0.25rem;
  }
</style>
