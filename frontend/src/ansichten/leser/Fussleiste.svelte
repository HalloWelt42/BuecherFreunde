<script lang="ts">
  // Untere Leiste: zurück, Schalter des Formats, Stand, Sprungbalken, weiter
  import type { Snippet } from "svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  let { anteil, anAnfang = false, amEnde = false, onzurueck, onvor, onanteil, schalter = undefined, children }: { anteil: number; anAnfang?: boolean; amEnde?: boolean; onzurueck: () => void; onvor: () => void; onanteil: (anteil: number) => void; schalter?: Snippet; children: Snippet } = $props();

  // Beim Ziehen läuft die Anzeige mit, gesprungen wird erst beim Loslassen
  let gezogen = $state<number | null>(null);
  let prozent = $derived(gezogen ?? Math.round(anteil * 1000) / 10);
</script>

<Knopf text="Vorige Seite" symbol="chevron-left" nur frei klein gesperrt={anAnfang} onclick={onzurueck} />
{@render schalter?.()}
{@render children()}
<input class="sprung" type="range" min="0" max="100" step="0.1" aria-label="Stelle im Buch" aria-valuetext="{Math.round(prozent)} Prozent" value={prozent} style:--anteil="{prozent}%"
  oninput={(e) => (gezogen = Number(e.currentTarget.value))}
  onchange={(e) => { onanteil(Number(e.currentTarget.value) / 100); gezogen = null; e.currentTarget.blur(); }} />
<Knopf text="Nächste Seite" symbol="chevron-right" nur frei klein gesperrt={amEnde} onclick={onvor} />
