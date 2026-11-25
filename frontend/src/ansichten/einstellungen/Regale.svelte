<script lang="ts">
  // Regale verwalten: anlegen, ändern, in die Leiste stellen, löschen
  import { aktualisiereKategorie, loescheKategorie } from "../../lib/api/categories";
  import { anzahl, zahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Regal } from "../../lib/typen";
  import Regalformular from "./Regalformular.svelte";

  let offen = $state<Regal | "neu" | null>(null);
  let wort = $state("");
  let passend = $derived(bestand.regale.filter((r) => r.name.toLowerCase().includes(wort.trim().toLowerCase())));

  $effect(() => void bestand.laden());

  async function stelleInLeiste(r: Regal) {
    try {
      await aktualisiereKategorie(r.id, { spezial: !r.spezial });
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
    }
  }

  async function loesche(r: Regal) {
    const ja = await frage({
      titel: `Regal ${r.name} löschen?`,
      folgen: [r.buch_anzahl ? `${anzahl(r.buch_anzahl, "Buch verliert", "Bücher verlieren")} dieses Regal, die Bücher selbst bleiben.` : "Kein Buch steht in diesem Regal.", "Farbe, Symbol und Beschreibung des Regals gehen verloren."],
      ja: "Regal löschen",
    });
    if (!ja) return;
    try {
      await loescheKategorie(r.id);
      melde.gut("Regal gelöscht");
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    }
  }
</script>

<Karte titel="Regale" symbol="folder-tree" id="regale">
  {#snippet neben()}<Knopf text="Neues Regal" symbol="plus" klein onclick={() => (offen = "neu")} />{/snippet}
  <input class="eingabe" type="search" placeholder="Regal suchen ({zahl(bestand.regale.length)})" aria-label="Regal suchen" bind:value={wort} />
  <div class="verwaltung">
    {#each passend as r (r.id)}
      <div class="stelle regalzeile">
        <span class="zeichenfeld"><Symbol name={r.icon || "folder"} farbe="color-mix(in srgb, {r.color || "#6b7280"} 70%, var(--tinte))" /></span>
        <span><b>{r.name}</b> <span class="leise zahl">{zahl(r.buch_anzahl)}</span>{#if r.name.startsWith("ai_")} <span class="marke-text info"><Symbol name="wand-magic-sparkles" />KI</span>{/if}{#if r.description}<br /><span class="leise">{r.description}</span>{/if}</span>
        <span class="reihe griffe">
          <Knopf text={r.spezial ? "Aus der Leiste nehmen" : "In der Leiste zeigen"} symbol="table-columns" nur klein frei gedrueckt={!!r.spezial} onclick={() => void stelleInLeiste(r)} />
          <Knopf text="Bearbeiten" symbol="pen" nur klein frei onclick={() => (offen = r)} />
          <Knopf text="Löschen" symbol="trash" nur klein frei onclick={() => void loesche(r)} />
        </span>
      </div>
    {:else}<p class="leise">{bestand.regale.length ? "Kein Regal heißt so." : "Noch kein Regal angelegt."}</p>{/each}
  </div>
</Karte>

{#if offen}<Regalformular regal={offen === "neu" ? null : offen} onschliessen={() => (offen = null)} />{/if}
