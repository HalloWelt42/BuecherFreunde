<script lang="ts">
  // Eine Datei, die nicht übernommen wird, mit Grund (BF-80); wartet sie noch, lässt sie sich als Material zu einem Werk
  // dieser Vorschau nehmen
  import { dateizeichen, endung, wartet } from "../../../lib/annahme/vorschau";
  import type { Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import { groesse } from "../../../lib/format";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { Vorschaustand } from "./vorschaustand.svelte";

  let { zeile, stand, offen, onmaterial }: { zeile: Vorschauzeile; stand: Vorschaustand; offen: boolean; onmaterial: (z: Vorschauzeile, anker: HTMLElement) => void } = $props();
  let anker = $state<HTMLElement | null>(null);
  let grund = $derived(zeile.felder?.nicht || zeile.text);
  let geht = $derived(stand.offen && wartet(zeile) && stand.werke.length > 0);
  let hinweis = $derived(!wartet(zeile) ? "Diese Datei wurde nicht ausgepackt" : !stand.werke.length ? "In dieser Vorschau gibt es kein Buch, zu dem sie gehören könnte" : "Als Begleitmaterial zu einem Buch dieser Vorschau");
</script>

<div class="nichtzeile">
  <span class="dateizeichen"><Symbol name={dateizeichen(zeile.name)} /></span>
  <span class="vdatei"><b title={[zeile.ordner, zeile.name].filter(Boolean).join("/")}>{zeile.name}</b><small>{#if zeile.ordner}<Symbol name="folder" /> {zeile.ordner}, {/if}{[endung(zeile.name), groesse(zeile.groesse)].filter(Boolean).join(", ")}</small></span>
  <span class="marke-text warn"><Symbol name="circle-info" />{grund}</span>
  <Knopf text="Als Material" symbol="paperclip" klein titel={hinweis} gesperrt={!geht} aufgeklappt={offen} bind:element={anker} onclick={() => anker && onmaterial(zeile, anker)} />
</div>
