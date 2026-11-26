<script lang="ts">
  // Ein Bereich als Kachel (BF-69): Kopf mit Zeichen und Zahl, darunter seine Kategorien mit Herkunft und Zahl. Antippen
  // bearbeitet, Kategorien lassen sich in einen anderen Bereich ziehen.
  import { zahl } from "../../../lib/format";
  import { farbeVon, geltungstext, herkunftszeichen } from "../../../lib/katalog";
  import { arten } from "../../../lib/stand/arten.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { Katalogbereich, Katalogkategorie } from "../../../lib/typen";

  interface Eigenschaften {
    bereich: Katalogbereich;
    /** Eine gezogene Kategorie aus einem anderen Bereich schwebt darüber */
    ziel?: boolean;
    onbereich: () => void;
    onkategorie: (k: Katalogkategorie) => void;
    onneu: () => void;
    onziehen: (k: Katalogkategorie | null) => void;
    onueber: (an: boolean) => void;
    onablegen: () => void;
  }
  let { bereich, ziel = false, onbereich, onkategorie, onneu, onziehen, onueber, onablegen }: Eigenschaften = $props();

  let gilt = $derived(geltungstext(bereich.arten, (a) => arten.typName(a)));
  let warum = $derived(bereich.verborgen ? [bereich.anzahl === 0 ? "keine Bücher" : "", "verborgen"].filter(Boolean).join(", ") : bereich.beschreibung);

  function ueber(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    onueber(true);
  }

  function verlassen(e: DragEvent) {
    if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node | null)) onueber(false);
  }

  function ablegen(e: DragEvent) {
    e.preventDefault();
    onablegen();
  }

  function beginne(e: DragEvent, k: Katalogkategorie) {
    e.dataTransfer?.setData("text/plain", k.name);
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
    onziehen(k);
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="bereichskachel platte" class:verborgen={bereich.verborgen} class:ziel ondragover={ueber} ondragleave={verlassen} ondrop={ablegen}>
  <button type="button" class="bereichskopf" title="{bereich.name} bearbeiten" onclick={onbereich}>
    <Katalogzeichen name={bereich.zeichen} farbe={bereich.farbe} groesse="gross" /><b>{bereich.name}</b>
    <span class="leise zahl">{#if bereich.verborgen}<Symbol name="eye-slash" />{:else if bereich.anzahl !== null}{zahl(bereich.anzahl)}{/if}</span>
  </button>
  {#if warum}<span class="warum">{warum}</span>{/if}
  {#if gilt}<span class="warum gilt">{gilt}</span>{/if}
  {#if !bereich.verborgen}
    {#if bereich.kategorien.length}
      <div class="kategorien">
        {#each bereich.kategorien as k (k.schluessel)}
          {@const herkunft = herkunftszeichen(k)}
          <button type="button" class="kategoriezeile" class:verborgen={k.verborgen} draggable="true" title="{k.name} bearbeiten" onclick={() => onkategorie(k)} ondragstart={(e) => beginne(e, k)} ondragend={() => onziehen(null)}>
            <Katalogzeichen name={k.zeichen} farbe={farbeVon(k, bereich)} groesse="klein" /><span class="name">{k.name}</span>
            <span class="herkunft" title={herkunft[1]}><Symbol name={herkunft[0]} /><span class="nur-vorlesen">{herkunft[1]}</span></span>
            <span class="leise zahl">{k.anzahl === null ? "" : zahl(k.anzahl)}</span>
          </button>
        {/each}
      </div>
    {/if}
    <span><Knopf text="Kategorie" symbol="plus" klein frei onclick={onneu} /></span>
  {/if}
</div>
