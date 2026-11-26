<script lang="ts">
  // Ein Begriff der Begriffsliste, neu oder geändert: bleibt englisch oder hat eine deutsche Form
  import { untrack } from "svelte";
  import { aendereBegriff, legeBegriffAn } from "../../lib/api/uebersetzung";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Begriff, Begriffsart, BegriffNeu } from "../../lib/uebersetzung/typen";

  interface Eigenschaften {
    buch: number;
    /** null: ein neuer Begriff */
    begriff: Begriff | null;
    /** Englische Begriffe, die schon in der Liste stehen (klein) */
    vorhanden: Set<string>;
    onschliessen: () => void;
    ongespeichert: (b: Begriff) => void;
  }
  let { buch, begriff, vorhanden, onschliessen, ongespeichert }: Eigenschaften = $props();

  const alt = untrack(() => begriff);
  let w = $state<BegriffNeu>({ englisch: alt?.englisch ?? "", deutsch: alt?.deutsch ?? "", bleibt: alt?.bleibt ?? false, grund: alt?.grund ?? "", art: alt?.art ?? "begriff" });
  let speichert = $state(false);
  const ARTEN: [Begriffsart, string][] = [["begriff", "Begriff"], ["einheit", "Einheit"]];

  let doppelt = $derived(!!w.englisch.trim() && w.englisch.trim().toLowerCase() !== alt?.englisch.toLowerCase() && vorhanden.has(w.englisch.trim().toLowerCase()));
  let fertig = $derived(!!w.englisch.trim() && (w.bleibt || !!w.deutsch.trim()) && !doppelt);

  async function speichern(e?: Event) {
    e?.preventDefault();
    if (!fertig || speichert) return;
    speichert = true;
    const daten = { ...w, englisch: w.englisch.trim(), deutsch: w.bleibt ? "" : w.deutsch.trim(), grund: w.grund.trim() };
    try {
      ongespeichert(alt ? await aendereBegriff(alt.id, daten) : await legeBegriffAn(buch, daten));
    } catch (f) {
      melde.schlecht(f, "Nicht gespeichert");
    } finally {
      speichert = false;
    }
  }
</script>

<Fenster titel={alt ? "Begriff bearbeiten" : "Neuer Begriff"} breite="30rem" {onschliessen}>
  <form class="begriffsformular" onsubmit={speichern}>
    <label class="feld">Englisch<input class="eingabe" bind:value={w.englisch} data-fokus autocomplete="off" spellcheck="false" /></label>
    {#if doppelt}<span class="marke-text warn"><Symbol name="circle-exclamation" />Steht schon in der Liste</span>{/if}
    <Haekchen text="Bleibt englisch" an={w.bleibt} onwahl={(an) => (w.bleibt = an)} />
    <label class="feld">Deutsch<input class="eingabe" bind:value={w.deutsch} disabled={w.bleibt} autocomplete="off" /></label>
    <label class="feld">Grund<input class="eingabe" bind:value={w.grund} autocomplete="off" /></label>
    <div class="feld">Art<Segment name="Art" werte={ARTEN} wert={w.art} onwahl={(a) => (w.art = a)} /></div>
    <button type="submit" hidden aria-hidden="true" tabindex="-1"></button>
  </form>
  {#snippet fuss()}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <Knopf text="Speichern" symbol="check" haupt laeuft={speichert} gesperrt={!fertig} onclick={() => void speichern()} />
    </span>
  {/snippet}
</Fenster>
