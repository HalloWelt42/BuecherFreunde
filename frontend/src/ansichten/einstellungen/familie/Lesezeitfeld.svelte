<script lang="ts">
  // Lesezeit eines Kindes: am Tag (mit der Vorgabe nach Alter), Ruhezeit und ob Vorlesen mitzählt. Die Werte stehen als
  // Chips; ein Tipp öffnet, womit sie sich ändern, oder schaltet die Grenze ganz aus.
  import type { Profil } from "../../../lib/api/familie";
  import { einstellungenVon, lesezeitVorgabe, minutenText, ruhezeitText, tageszeitText, vorgabeText } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Regler from "../../../lib/teile/Regler.svelte";
  import Schalter from "../../../lib/teile/Schalter.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { setze } from "./aendern";
  import Wertchip from "./Wertchip.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  const VON = 5;
  const BIS = 180;
  const SCHRITT = 5;
  /** Der Regler speichert erst, wenn er kurz stillsteht */
  const WARTE_MS = 400;

  let regel = $derived(einstellungenVon(profil, familie.stufen.stufen).lesezeit);
  let vorgabe = $derived(lesezeitVorgabe(profil.geburtsjahr, familie.stufen.lesezeit));
  let entwurf = $state<number | null>(null);
  /** Ohne eigenen Wert die Vorgabe nach Alter, sonst die kleinste der Leitlinie */
  let minuten = $derived(entwurf ?? (regel.minuten || vorgabe?.minuten || familie.stufen.lesezeit[0]?.minuten || VON));
  let uhr: ReturnType<typeof setTimeout> | undefined;

  function ziehe(w: number) {
    entwurf = w;
    clearTimeout(uhr);
    uhr = setTimeout(() => void setze(profil, "lesezeit", { minuten: w }).then(() => (entwurf = null)), WARTE_MS);
  }

  $effect(() => () => clearTimeout(uhr));
</script>

<section class="elternfeld platte">
  <h3><Symbol name="clock" />Lesezeit</h3>
  <div class="elternzeile">
    <span>Am Tag{#if vorgabe}<small>{vorgabeText(vorgabe)}</small>{/if}</span>
    <Wertchip text={tageszeitText(regel)} name="Lesezeit am Tag" gesperrt={!aendert}>
      <div class="elternzeile"><span>Grenze am Tag</span><Schalter an={regel.an} name="Grenze am Tag" onwahl={(an) => void setze(profil, "lesezeit", { an, minuten })} /></div>
      {#if regel.an}
        <Regler name="Minuten" wert={minuten} von={VON} bis={BIS} schritt={SCHRITT} anzeige={minutenText(minuten)} onwahl={ziehe} />
        {#if vorgabe && vorgabe.minuten !== regel.minuten}<Knopf text="Vorgabe: {minutenText(vorgabe.minuten)}" symbol="rotate-left" klein onclick={() => void setze(profil, "lesezeit", { an: vorgabe.an, minuten: vorgabe.minuten })} />{/if}
      {/if}
    </Wertchip>
  </div>
  <div class="elternzeile">
    <span>Ruhezeit<small>eine Stunde vor dem Schlafen</small></span>
    <Wertchip text={ruhezeitText(regel)} name="Ruhezeit" gesperrt={!aendert}>
      <div class="elternzeile"><span>Ruhezeit</span><Schalter an={regel.ruhe_an} name="Ruhezeit" onwahl={(an) => void setze(profil, "lesezeit", { ruhe_an: an })} /></div>
      {#if regel.ruhe_an}
        <div class="zeiten">
          <label class="feld">Ab<input class="eingabe" type="time" value={regel.ruhe_von} onchange={(e) => void setze(profil, "lesezeit", { ruhe_von: e.currentTarget.value })} /></label>
          <label class="feld">Bis<input class="eingabe" type="time" value={regel.ruhe_bis} onchange={(e) => void setze(profil, "lesezeit", { ruhe_bis: e.currentTarget.value })} /></label>
        </div>
      {/if}
    </Wertchip>
  </div>
  <div class="elternzeile">
    <span>Vorlesen zählt mit</span>
    <Schalter an={regel.vorlesen_zaehlt} name="Vorlesen zählt mit" gesperrt={!aendert} onwahl={(an) => void setze(profil, "lesezeit", { vorlesen_zaehlt: an })} />
  </div>
</section>

<style>
  .zeiten {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
</style>
