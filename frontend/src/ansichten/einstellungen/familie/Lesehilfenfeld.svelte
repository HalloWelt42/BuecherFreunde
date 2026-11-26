<script lang="ts">
  // Lesehilfen je Kind (Entwurf kinder-5 Abschnitt 5): Vorlesen mit Mitlesen samt Tempo, farbige Silben, Lesezeile, Hinweise
  // vorsprechen, Tasten ansagen und ihre Stimme, die Schrift. Silben und Lesezeile schaltet das Kind danach selbst an und aus;
  // hier steht, ob es sie hat. Ohne Wahl der Eltern gilt die Vorgabe der Stufe. Die Schrift (Entwurf kinder-7, BF-88): ihre
  // Größe und ob normal oder Kinderschrift; in der Gestaltung groß schaltet das Kind beim Lesen selbst um.
  import type { Profil } from "../../../lib/api/familie";
  import { LESESCHRIFTEN, SCHRIFTEN, TEMPI, einstellungenVon, gestaltungText, leseschriftText, schriftText, tempoText } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";
  import Schalter from "../../../lib/teile/Schalter.svelte";
  import Segment from "../../../lib/teile/Segment.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { setze } from "./aendern";
  import Ansagestimme from "./Ansagestimme.svelte";
  import Wahlfeld from "./Wahlfeld.svelte";
  import Wertchip from "./Wertchip.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  let einstellungen = $derived(einstellungenVon(profil, familie.stufen.stufen));
  let hilfen = $derived(einstellungen.lesehilfen);
  /** Was die Stufe vorgibt: ihre Gestaltung mit ihrer Schrift, etwa Groß mit Normal */
  let stufe = $derived(familie.stufen.stufen.find((s) => s.schluessel === profil.stufe)?.vorgaben);
  let schriftvorgabe = $derived(stufe?.gestaltung && stufe.lesehilfen?.schrift_wahl ? `Vorgabe in ${gestaltungText(stufe.gestaltung)}: ${leseschriftText(stufe.lesehilfen.schrift_wahl)}` : "");
  let tempoOffen = $state(false);
  let tempoKnopf = $state<HTMLElement | null>(null);
  /** Das Tempo als Wort des Segments, je Wert der nächstgelegene */
  let tempoWort = $derived(tempoText(hilfen.tempo));
  const tempoWerte = TEMPI.map(([, wort]) => [wort, wort] as [string, string]);
</script>

<section class="elternfeld platte">
  <h3><Symbol name="hands-holding-child" />Lesehilfen</h3>
  <div class="elternzeile">
    <span>Vorlesen mit Mitlesen<small><button type="button" class="unterwahl" bind:this={tempoKnopf} aria-expanded={tempoOffen} disabled={!aendert} onclick={() => (tempoOffen = !tempoOffen)}>Tempo: {tempoWort}<Symbol name="chevron-down" /></button></small></span>
    <Schalter an={hilfen.mitlesen} name="Vorlesen mit Mitlesen" gesperrt={!aendert} onwahl={(mitlesen) => void setze(profil, "lesehilfen", { mitlesen })} />
  </div>
  <div class="elternzeile">
    <span>Farbige Silben<small>{profil.name} kann sie selbst an- und ausschalten</small></span>
    <Schalter an={hilfen.silben} name="Farbige Silben" gesperrt={!aendert} onwahl={(silben) => void setze(profil, "lesehilfen", { silben })} />
  </div>
  <div class="elternzeile">
    <span>Lesezeile</span>
    <Schalter an={hilfen.lesezeile} name="Lesezeile" gesperrt={!aendert} onwahl={(lesezeile) => void setze(profil, "lesehilfen", { lesezeile })} />
  </div>
  <div class="elternzeile">
    <span>Hinweise vorsprechen<small>Lesezeit, Ruhezeit, Bild-PIN und alles, was sonst nur da steht</small></span>
    <Schalter an={hilfen.hinweise_sprechen} name="Hinweise vorsprechen" gesperrt={!aendert} onwahl={(hinweise_sprechen) => void setze(profil, "lesehilfen", { hinweise_sprechen })} />
  </div>
  <div class="elternzeile">
    <span>Tasten ansagen<small>sagt, was gerade gedrückt wurde</small></span>
    <Schalter an={hilfen.tasten_ansagen} name="Tasten ansagen" gesperrt={!aendert} onwahl={(tasten_ansagen) => void setze(profil, "lesehilfen", { tasten_ansagen })} />
  </div>
  <Ansagestimme {profil} {aendert} />
  <div class="elternzeile trenn">
    <span>Schrift{#if schriftvorgabe}<small>{schriftvorgabe}</small>{/if}</span>
    <Wertchip text="Aa {schriftText(hilfen.schrift)}" name="Größe der Schrift" gesperrt={!aendert}>
      <Segment name="Größe der Schrift" werte={SCHRIFTEN} wert={hilfen.schrift} onwahl={(schrift) => void setze(profil, "lesehilfen", { schrift })} />
    </Wertchip>
  </div>
  {#if einstellungen.gestaltung}
    <Wahlfeld name="Schrift" werte={LESESCHRIFTEN} wert={hilfen.schrift_wahl} breit gesperrt={!aendert} onwahl={(schrift_wahl) => void setze(profil, "lesehilfen", { schrift_wahl })} />
  {/if}
</section>

{#if tempoOffen}
  <Menue anker={tempoKnopf} name="Tempo beim Vorlesen" breite="17rem" onschliessen={() => (tempoOffen = false)}>
    <div class="ganz"><Segment name="Tempo beim Vorlesen" werte={tempoWerte} wert={tempoWort} onwahl={(w) => void setze(profil, "lesehilfen", { tempo: TEMPI.find(([, wort]) => wort === w)?.[0] ?? 1 })} /></div>
  </Menue>
{/if}

<style>
  .ganz :global(.segment) {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
  }
</style>
