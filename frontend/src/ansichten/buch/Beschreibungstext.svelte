<script lang="ts">
  // Aus dem Buchtext: die ersten Seiten holen, zur Beschreibung zurechtkürzen, übernehmen; beim Bearbeiten ins Formular, auf der
  // Buchseite gleich ins Buch (ziel.ts)
  import { ladeVolltext } from "../../lib/api/metadata";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Angabenziel } from "./ziel";

  let { buchId, ziel, onschliessen }: { buchId: number; ziel: Angabenziel; onschliessen: () => void } = $props();

  let von = $state("1");
  let bis = $state("5");
  let gesamt = $state(0);
  let text = $state("");
  let laedt = $state(false);
  let speichert = $state(false);
  let hinweis = $state("");

  const seite = (w: string, vorgabe: number) => Math.max(1, Number.parseInt(w, 10) || vorgabe);

  async function hole() {
    laedt = true;
    hinweis = "";
    try {
      const a = await ladeVolltext(buchId, seite(von, 1), Math.max(seite(von, 1), seite(bis, 5)));
      text = a.volltext ?? "";
      gesamt = a.seiten_gesamt ?? 0;
      von = String(a.seite_von ?? von);
      bis = String(a.seite_bis ?? bis);
      if (!text) hinweis = "Auf diesen Seiten steht kein Text.";
    } catch (e) {
      hinweis = e instanceof Error ? e.message : String(e);
    } finally {
      laedt = false;
    }
  }

  async function uebernimm() {
    speichert = true;
    try {
      await ziel.beschreibung(text.trim());
      onschliessen();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      speichert = false;
    }
  }

  $effect(() => void hole());
</script>

<Fenster titel="Aus dem Buchtext" breite="40rem" {onschliessen}>
  <form class="reihe" onsubmit={(e) => { e.preventDefault(); void hole(); }}>
    <label class="reihe leise">Seite<input class="eingabe kurz" inputmode="numeric" bind:value={von} /></label>
    <label class="reihe leise">bis<input class="eingabe kurz" inputmode="numeric" bind:value={bis} /></label>
    {#if gesamt}<span class="leise zahl">von {gesamt}</span>{/if}
    <Knopf text="Laden" symbol="rotate" klein art="submit" laeuft={laedt} />
  </form>
  {#if hinweis}<p class="marke-text warn" role="status">{hinweis}</p>{/if}
  <textarea class="eingabe" rows="8" aria-label="Beschreibung" bind:value={text}></textarea>
  {#if !ziel.sofort}<p class="leise">Kommt ins Formular, ins Buch erst mit Speichern.</p>{/if}
  {#snippet fuss()}
    <div class="fensterfuss">
      <span class="tasten2">
        <Knopf text="Verwerfen" symbol="xmark" onclick={onschliessen} />
        <Knopf text="Als Beschreibung übernehmen" symbol="check" haupt gesperrt={!text.trim()} laeuft={speichert} onclick={() => void uebernimm()} />
      </span>
    </div>
  {/snippet}
</Fenster>

<style>
  .kurz {
    width: 4.5rem;
  }
</style>
