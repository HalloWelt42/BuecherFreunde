<script lang="ts">
  // Ein fehlender Band im Regal der Sammlung (BF-75): blasser Umschlag mit der Nummer, darunter "Band n fehlt" und der Titel,
  // wenn die Quellen ihn kennen. Ein Tipp öffnet das Feld zum Band; Dateien lassen sich direkt darauf ziehen.
  import type { Luecke } from "../../lib/api/luecken";
  import Deckblatt from "../../lib/teile/Deckblatt.svelte";

  let { luecke, autor, offen, onoeffnen, onabgelegt }: { luecke: Luecke; autor: string; offen: boolean; onoeffnen: (anker: HTMLElement) => void; onabgelegt?: (e: DragEvent) => void } = $props();
  let knopf: HTMLButtonElement | undefined = $state();
  let ueber = $state(false);
  let blatt = $derived({ id: luecke.nummer, title: luecke.titel || `Band ${luecke.nummer}`, author: luecke.autor || autor });

  const mitDateien = (e: DragEvent) => !!onabgelegt && !!e.dataTransfer?.types.includes("Files");
</script>

<div class="band luecke" class:ueber>
  <button type="button" class="flaeche" aria-expanded={offen} aria-label="Band {luecke.nummer} fehlt{luecke.titel ? `: ${luecke.titel}` : ''}" bind:this={knopf}
    onclick={() => knopf && onoeffnen(knopf)}
    ondragover={(e) => { if (mitDateien(e)) { e.preventDefault(); e.stopPropagation(); ueber = true; } }}
    ondragleave={() => (ueber = false)}
    ondrop={(e) => { if (mitDateien(e)) { e.preventDefault(); e.stopPropagation(); ueber = false; onabgelegt?.(e); } }}>
    <span class="stand"><span class="umschlag platzhalter"><Deckblatt buch={blatt} /><span class="nummer">{luecke.nummer}</span></span></span>
    <span class="boden"></span>
    <span class="schild"><span class="bandnr">Band {luecke.nummer} fehlt</span><b>{luecke.titel || "Titel unbekannt"}</b></span>
  </button>
</div>
