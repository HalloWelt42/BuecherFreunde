<script lang="ts">
  // Stufe eines Kindes: fünf gleich breite Felder, darunter der Vorschlag aus dem Geburtsjahr. Dazu die Gestaltung des
  // Kinderbereichs (BF-88): Klein oder Groß, Vorgabe aus der Stufe, je Kind umstellbar; die Fähigkeiten bleiben an der Stufe.
  // Eine Stufe ohne Gestaltung (Jugend) liest in der Oberfläche der App, dort gibt es keine Wahl.
  import type { Profil, Stufe } from "../../../lib/api/familie";
  import { einstellungenVon, GESTALTUNGEN, gestaltungText, stufeVorschlag } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Segment from "../../../lib/teile/Segment.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import { aendere, waehle } from "./aendern";
  import Wahlfeld from "./Wahlfeld.svelte";

  let { profil, aendert }: { profil: Profil; aendert: boolean } = $props();

  let werte = $derived(familie.stufen.stufen.map((s) => [s.schluessel, s.name] as [Stufe, string]));
  let vorschlag = $derived(stufeVorschlag(profil.geburtsjahr, familie.stufen.stufen));
  /** Die Gestaltung, die die Stufe vorgibt; null: die Oberfläche der App */
  let vorgabe = $derived(familie.stufen.stufen.find((s) => s.schluessel === profil.stufe)?.vorgaben?.gestaltung ?? null);
  let gestaltung = $derived(einstellungenVon(profil, familie.stufen.stufen).gestaltung);
</script>

<section class="elternfeld platte">
  <h3><Symbol name="stairs" />Stufe</h3>
  {#if werte.length}
    <div class="stufenwahl"><Segment name="Stufe" {werte} wert={profil.stufe ?? werte[0][0]} gesperrt={!aendert} onwahl={(stufe) => void aendere(profil, { stufe })} /></div>
  {/if}
  <span class="hinweis">{vorschlag ? `Vorschlag aus dem Geburtsjahr: ${vorschlag.name}. ` : ""}Die Stufe bestimmt Funktionen und Vorgaben unten; jede lässt sich einzeln ändern.</span>
  {#if vorgabe && gestaltung}
    <div class="elternzeile trenn">
      <span>Gestaltung<small>Vorgabe aus der Stufe: {gestaltungText(vorgabe)}</small></span>
      <Wahlfeld name="Gestaltung" werte={GESTALTUNGEN} wert={gestaltung} gesperrt={!aendert} onwahl={(g) => void waehle(profil, "gestaltung", g)} />
    </div>
    <span class="hinweis"><Symbol name="circle-info" /> Klein ist verspielt mit großen Tasten, Groß ruhig wie die App, anfangs ohne Katze und Ansagen. Was {profil.name} darf, bleibt an der Stufe.</span>
  {/if}
</section>
