<script lang="ts">
  // Sammlungen verwalten
  import { loescheSammlung } from "../../lib/api/collections";
  import { anzahl, zahl } from "../../lib/format";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Sammlung } from "../../lib/typen";
  import Sammlungsformular from "./Sammlungsformular.svelte";

  let offen = $state<Sammlung | "neu" | null>(null);

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
