<script lang="ts">
  // Eine Stelle mit berichtigten Marken im Prüfbericht (wie eine offene Stelle, Entwurf Abschnitt 4): Englisch und Deutsch
  // nebeneinander, darunter jede Reparatur mit dem Text, der seine Marke verlor. Nichts zu entscheiden.
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { reparaturtext } from "../../lib/uebersetzung/texte";
  import type { Stelle } from "../../lib/uebersetzung/typen";
  import Markentext from "./Markentext.svelte";

  let { stelle }: { stelle: Stelle } = $props();
  let reparaturen = $derived(stelle.reparaturen ?? []);
</script>

<article class="offenestelle platte" aria-label={stelle.ort}>
  <div class="reihe"><b>{stelle.ort}</b>{#if stelle.seite_original}<span class="leise">Seite {stelle.seite_gedruckt || stelle.seite_original} im Original</span>{/if}</div>
  <div class="stellenpaar">
    <div lang="en"><small>Englisch</small><Markentext text={stelle.original} /></div>
    <div lang="de"><small>Deutsch</small><Markentext text={stelle.deutsch} /></div>
  </div>
  {#each reparaturen as r, n (n)}
    <div class="befundzeile"><Symbol name="screwdriver-wrench" /><span>{reparaturtext(r)}</span></div>
  {/each}
</article>
