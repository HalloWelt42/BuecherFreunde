<script lang="ts">
  // Stufe eines Kindes: fünf gleich breite Felder, darunter der Vorschlag aus dem Geburtsjahr
  import type { Profil, Stufe } from "../../../lib/api/familie";
  import { stufeVorschlag } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Segment from "../../../lib/teile/Segment.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { aendere } from "./aendern";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  let werte = $derived(familie.stufen.stufen.map((s) => [s.schluessel, s.name] as [Stufe, string]));
  let vorschlag = $derived(stufeVorschlag(profil.geburtsjahr, familie.stufen.stufen));
</script>

<section class="elternfeld platte">
  <h3><Symbol name="stairs" />Stufe</h3>
  {#if werte.length}
    <div class="stufenwahl"><Segment name="Stufe" {werte} wert={profil.stufe ?? werte[0][0]} gesperrt={!aendert} onwahl={(stufe) => void aendere(profil, { stufe })} /></div>
  {/if}
  <span class="hinweis">{vorschlag ? `Vorschlag aus dem Geburtsjahr: ${vorschlag.name}. ` : ""}Die Stufe bestimmt Aussehen, Funktionen und Vorgaben unten; jede lässt sich einzeln ändern.</span>
</section>
