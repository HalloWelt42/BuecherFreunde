<script lang="ts">
  // Beschreibung aus den ersten Seiten: holen, zurechtkürzen, übernehmen
  import { ladeVolltext, uebernehmMetadaten } from "../../lib/api/metadata";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln } from "../../lib/typen";

  let { buch, onfertig, onabbruch }: { buch: BuchEinzeln; onfertig: () => void; onabbruch: () => void } = $props();

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
      const a = await ladeVolltext(buch.id, seite(von, 1), Math.max(seite(von, 1), seite(bis, 5)));
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
      await uebernehmMetadaten(buch.id, { beschreibung: text.trim() });
      melde.gut("Beschreibung übernommen");
      onfertig();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      speichert = false;
    }
  }

  $effect(() => void hole());
</script>

<form class="mulde karte" onsubmit={(e) => { e.preventDefault(); void hole(); }}>
  <div class="reihe">
    <label class="reihe leise">Seite<input class="eingabe kurz" inputmode="numeric" bind:value={von} /></label>
    <label class="reihe leise">bis<input class="eingabe kurz" inputmode="numeric" bind:value={bis} /></label>
    {#if gesamt}<span class="leise zahl">von {gesamt}</span>{/if}
    <Knopf text="Laden" symbol="rotate" klein art="submit" laeuft={laedt} />
  </div>
  {#if hinweis}<p class="marke-text warn" role="status">{hinweis}</p>{/if}
  <textarea class="eingabe" rows="8" aria-label="Beschreibung" bind:value={text}></textarea>
  <div class="reihe">
    <Knopf text="Als Beschreibung übernehmen" symbol="check" klein haupt gesperrt={!text.trim()} laeuft={speichert} onclick={() => void uebernimm()} />
    <Knopf text="Verwerfen" symbol="xmark" klein onclick={onabbruch} />
  </div>
</form>

<style>
  .kurz {
    width: 4.5rem;
  }
</style>
