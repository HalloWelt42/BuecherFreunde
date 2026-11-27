<script lang="ts">
  // Ein Buch mit ISBN zur Wahl (BF-111): Haken, Umschlag, Titel und Autor, die beste ISBN mit Fundstelle und Stufe, Annehmen und
  // Ablehnen. Ein Tippen auf die Nummer zeigt alle Kandidaten des Buchs im Fenster "ISBN im Buch".
  import type { Isbnwahl } from "../../../lib/api/imports";
  import Auszug from "../../../lib/teile/Auszug.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Umschlag from "../../../lib/teile/Umschlag.svelte";
  import { FUNDORTE, STUFEN } from "../../buch/isbn";
  import { stellenort } from "../../buch/stelle";

  interface Eigenschaften {
    zeile: Isbnwahl;
    an: boolean;
    arbeitet: boolean;
    onhake: (an: boolean) => void;
    onansehen: () => void;
    onannehmen: () => void;
    onablehnen: () => void;
  }
  let { zeile, an, arbeitet, onhake, onansehen, onannehmen, onablehnen }: Eigenschaften = $props();

  let b = $derived(zeile.buch);
  let k = $derived(zeile.kandidat);
  let e = $derived(k.quelle ?? k.text);
  let stelle = $derived(k.stellen.find((s) => s.fundort === k.fundort) ?? k.stellen[0]);
  let wo = $derived(stelle ? `, ${FUNDORTE[stelle.fundort]}, ${stellenort(b, stelle)}` : "");
</script>

<div class="vorschlagszeile platte isbnwahl" class:arbeitet>
  <span class="wahl"><Haekchen name="{b.title} auswählen" {an} gesperrt={arbeitet} onwahl={onhake} /></span>
  <a class="bild" href="/book/{b.id}" title="{b.title} öffnen"><Umschlag buch={b} /></a>
  <span class="titel"><b title={b.title}>{b.title}</b><small>{b.author}</small></span>
  <span class="grund">
    <button type="button" class="auch" title="Alle ISBN in diesem Buch ansehen" onclick={onansehen}><Symbol name="barcode" /><span class="zahl">{k.isbn}{zeile.weitere ? ` und ${zeile.weitere} weitere` : ""}{wo}</span></button>
    <span><Symbol name={STUFEN[e.stufe].symbol} /><span><span class="marke-text {STUFEN[e.stufe].klasse}">{STUFEN[e.stufe].wort}</span> {e.basis}: <Auszug text={e.was} />{e.warum ? `, ${e.warum}` : ""}</span></span>
  </span>
  <span class="reihe tun">
    <Knopf text="Annehmen" symbol="check" nur klein frei laeuft={arbeitet} onclick={onannehmen} />
    <Knopf text="Ablehnen" symbol="xmark" nur klein frei gesperrt={arbeitet} onclick={onablehnen} />
  </span>
</div>
