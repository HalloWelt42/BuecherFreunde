<script lang="ts">
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Etikett } from "../../lib/typen";
  let { sitzung, e }: { sitzung: Lesesitzung; e: Etikett & { page_reference?: string; position_percent?: number; cfi_reference?: string } } = $props();

  function springe() {
    sitzung.griffe?.zurStelle(e.page_reference ?? "", e.cfi_reference ?? "", e.position_percent ?? 0);
    if (schale.telefon) sitzung.feld = "";
  }
</script>

<div class="stellenkarte" style:--f={e.color}>
  <input class="eingabe" placeholder="Name" aria-label="Name des Etiketts" maxlength="50" value={e.name} oninput={(x) => sitzung.aendereEtikett(e.id, { name: x.currentTarget.value })} />
  <textarea class="eingabe" rows="2" placeholder="Notiz" aria-label="Notiz zum Etikett" value={e.note} oninput={(x) => sitzung.aendereEtikett(e.id, { note: x.currentTarget.value })}></textarea>
  <div class="reihe">
    <Knopf text={e.page_reference || (e.position_percent ? `${Math.round(e.position_percent)} %` : "Zur Stelle")} symbol="arrow-right" klein frei onclick={springe} />
    <Knopf text="Etikett löschen" symbol="trash" nur klein frei onclick={() => void sitzung.loescheEtikett(e)} />
  </div>
</div>
