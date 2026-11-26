<script lang="ts">
  // Sammlungen verwalten
  import { ladeSammlungseinstellungen, loescheSammlung, speichereSammlungseinstellungen } from "../../lib/api/collections";
  import { anzahl, zahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Sammlung } from "../../lib/typen";
  import Sammlungsformular from "./Sammlungsformular.svelte";
  import { GRENZE_AB, GRENZE_BIS, grenzeAus } from "./sammlungsgrenze";

  let offen = $state<Sammlung | "neu" | null>(null);
  /** Ab so vielen Büchern steht eine Sammlung als ein Eintrag in der Bibliothek (BF-66) */
  let grenze = $state<number | null>(null);
  let gespeichert: number | null = null;

  $effect(() => {
    ladeSammlungseinstellungen()
      .then((e) => (grenze = gespeichert = e.als_eintrag_ab))
      .catch((e) => melde.schlecht(e, "Grenze nicht geladen"));
  });

  async function speichereGrenze() {
    const n = grenzeAus(grenze);
    if (n === null) {
      melde.warn(`Eine ganze Zahl von ${GRENZE_AB} bis ${GRENZE_BIS}`);
      grenze = gespeichert;
      return;
    }
    if (n === gespeichert) return;
    try {
      grenze = gespeichert = (await speichereSammlungseinstellungen({ als_eintrag_ab: n })).als_eintrag_ab;
      melde.gut(`Sammlungen ab ${n} Büchern als ein Eintrag`);
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
      grenze = gespeichert;
    }
  }

  async function loesche(s: Sammlung) {
    const ja = await frage({
      titel: `Sammlung ${s.name} löschen?`,
      folgen: [s.buch_anzahl ? `${anzahl(s.buch_anzahl, "Buch verliert", "Bücher verlieren")} die Sammlung und die Bandnummer, die Bücher selbst bleiben.` : "Kein Buch gehört zu dieser Sammlung.", "Farbe und Beschreibung der Sammlung gehen verloren."],
      ja: "Sammlung löschen",
    });
    if (!ja) return;
    try {
      await loescheSammlung(s.id);
      melde.gut("Sammlung gelöscht");
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    }
  }
</script>

<Karte titel="Sammlungen" symbol="layer-group" id="sammlungen">
  {#snippet neben()}<Knopf text="Neue Sammlung" symbol="plus" klein onclick={() => (offen = "neu")} />{/snippet}
  <label class="reihe grenzfeld">Sammlung als ein Eintrag ab <input class="eingabe" type="number" min={GRENZE_AB} max={GRENZE_BIS} step="1" disabled={grenze === null} bind:value={grenze} onchange={() => void speichereGrenze()} /> Büchern</label>
  <div class="verwaltung">
    {#each bestand.sammlungen as s (s.id)}
      <div class="stelle regalzeile">
        <span class="zeichenfeld"><span class="farbe" style:background={s.color}></span></span>
        <span><a class="sammlungsname" href="/collection/{s.id}" title="Sammlung öffnen">{s.name}</a> <span class="leise zahl">{zahl(s.buch_anzahl)}</span>{#if s.description}<br /><span class="leise">{s.description}</span>{/if}</span>
        <span class="reihe griffe">
          <Knopf text="Bearbeiten" symbol="pen" nur klein frei onclick={() => (offen = s)} />
          <Knopf text="Löschen" symbol="trash" nur klein frei onclick={() => void loesche(s)} />
        </span>
      </div>
    {:else}<p class="leise">Noch keine Sammlung angelegt.</p>{/each}
  </div>
</Karte>

{#if offen}<Sammlungsformular sammlung={offen === "neu" ? null : offen} onschliessen={() => (offen = null)} />{/if}
