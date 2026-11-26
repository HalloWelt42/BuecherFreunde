<script lang="ts">
  // Fläche eines Schritts, die allein rollt, und der Fuß mit Zurück, Überspringen und Weiter. In der Karte vor der Anmeldung und
  // in der Bühne (Wartung) dieselben Teile.
  import type { Snippet } from "svelte";
  import type { Weiterwahl } from "../../lib/einrichtung/ablauf";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  interface Eigenschaften {
    /** false: kein Weiter (der Schritt wartet auf etwas anderes) */
    weiter?: Weiterwahl | false;
    ueberspringen?: boolean;
    /** false: kein Zurück; "gesperrt": steht da, geht gerade nicht (ein Auftrag läuft) */
    zurueck?: boolean | "gesperrt";
    children: Snippet;
  }
  let { weiter = {}, ueberspringen = false, zurueck = true, children }: Eigenschaften = $props();

  /** Vom ersten Schritt zurück geht es nur in der Ersteinrichtung, dort zu den Ausgangslagen */
  let zurueckGeht = $derived(zurueck === true && !(einrichtung.ersterSchritt && !einrichtung.ersteinrichtung));

  function weiterTun() {
    const w = weiter || {};
    void einrichtung.tu(w.tun ?? (() => einrichtung.weiter()));
  }
</script>

<div class={einrichtung.wartung ? "inhalt rollen ew-schritt" : "ew-schritt rollen"}>{@render children()}</div>
<footer class="ew-fuss">
  {#if zurueck}<Knopf text="Zurück" symbol="chevron-left" klasse="ew-zurueck" titel="Zurück" gesperrt={!zurueckGeht || einrichtung.arbeitet} onclick={() => einrichtung.zurueck()} />{/if}
  <span class="ew-rechts">
    {#if ueberspringen}
      <Knopf text="Überspringen" symbol="forward" klasse="ew-ueberspringen" titel="Überspringen, später unter Einstellungen" gesperrt={einrichtung.arbeitet} onclick={() => void einrichtung.tu(() => einrichtung.ueberspringen())} />
    {/if}
    {#if weiter}
      <Knopf text={weiter.text ?? "Weiter"} symbol={weiter.symbol ?? "chevron-right"} haupt gesperrt={weiter.gesperrt} laeuft={einrichtung.arbeitet} titel={weiter.titel} onclick={weiterTun} />
    {/if}
  </span>
</footer>
