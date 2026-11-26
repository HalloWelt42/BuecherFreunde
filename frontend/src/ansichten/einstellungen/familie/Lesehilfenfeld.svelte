<script lang="ts">
  // Lesehilfen je Kind: Vorlesen mit Mitlesen samt Tempo, farbige Silben, Lesezeile, Größe der Kinderschrift. Silben und
  // Lesezeile schaltet das Kind danach selbst an und aus; hier steht, ob es sie hat.
  import type { Profil } from "../../../lib/api/familie";
  import { SCHRIFTEN, TEMPI, einstellungenVon, schriftText, tempoText } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";
  import Schalter from "../../../lib/teile/Schalter.svelte";
  import Segment from "../../../lib/teile/Segment.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { setze } from "./aendern";
  import Wertchip from "./Wertchip.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  let hilfen = $derived(einstellungenVon(profil, familie.stufen.stufen).lesehilfen);
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
    <span>Schrift<small>Kinderschrift, {schriftText(hilfen.schrift)}</small></span>
    <Wertchip text="Aa {schriftText(hilfen.schrift)}" name="Größe der Kinderschrift" gesperrt={!aendert}>
      <Segment name="Größe der Kinderschrift" werte={SCHRIFTEN} wert={hilfen.schrift} onwahl={(schrift) => void setze(profil, "lesehilfen", { schrift })} />
    </Wertchip>
  </div>
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
