<script lang="ts">
  // Untere Leiste: zurück, Schalter des Formats, Stand, Sprungbalken, weiter. Am Telefon (BF-63, Entwurf telefonleiste,
  // Vorschlag A) dazu vorige und nächste Stelle mit Notiz, Markierung oder Etikett; der Sprungbalken wird dort zur Linie
  // oben an der Leiste über die ganze Breite, so bleibt die Reihe in einer Zeile.
  import type { Snippet } from "svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Stellensprung from "./Stellensprung.svelte";
  let { anteil, anAnfang = false, amEnde = false, onzurueck, onvor, onanteil, schalter = undefined, sitzung = undefined, children }: { anteil: number; anAnfang?: boolean; amEnde?: boolean; onzurueck: () => void; onvor: () => void; onanteil: (anteil: number) => void; schalter?: Snippet; sitzung?: Lesesitzung; children: Snippet } = $props();

  // Beim Ziehen läuft die Anzeige mit, gesprungen wird erst beim Loslassen
  let gezogen = $state<number | null>(null);
  let prozent = $derived(gezogen ?? Math.round(anteil * 1000) / 10);
  let stellen = $derived(schale.telefon && !!sitzung);
</script>

<Knopf text="Vorige Seite" symbol="chevron-left" nur frei klein gesperrt={anAnfang} onclick={onzurueck} />
{@render schalter?.()}
{#if stellen && sitzung}<Stellensprung {sitzung} richtung={-1} />{/if}
{@render children()}
{#if stellen && sitzung}<Stellensprung {sitzung} richtung={1} />{/if}
<input class="sprung" class:oben={schale.telefon} type="range" min="0" max="100" step="0.1" aria-label="Stelle im Buch" aria-valuetext="{Math.round(prozent)} Prozent" value={prozent} style:--anteil="{prozent}%"
  oninput={(e) => (gezogen = Number(e.currentTarget.value))}
  onchange={(e) => { onanteil(Number(e.currentTarget.value) / 100); gezogen = null; e.currentTarget.blur(); }} />
<Knopf text="Nächste Seite" symbol="chevron-right" nur frei klein gesperrt={amEnde} onclick={onvor} />
