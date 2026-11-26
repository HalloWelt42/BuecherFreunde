<script lang="ts">
  // Ein Vorschlag für eine Sammlung (BF-66): Name, Anzahl, Autor, Fundwege, Satz der KI, Umschläge, dann Anlegen, Anpassen, Verwerfen
  import { anzahl } from "../../lib/format";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Sammlungsvorschlag } from "../../lib/typen";
  import { kiSatz, umschlagreihe, vorschlaege, wegSymbol } from "./sammlungsvorschlaege.svelte";

  let { vorschlag, onanpassen }: { vorschlag: Sammlungsvorschlag; onanpassen: () => void } = $props();

  let reihe = $derived(umschlagreihe(vorschlag.buecher));
  let ki = $derived(kiSatz(vorschlag.ki, vorschlag.ki_geprueft));
  let arbeitet = $derived(vorschlaege.arbeitet.has(vorschlag.id));
</script>

<div class="vorschlag platte">
  <div class="kopf"><b>{vorschlag.name}</b><span class="leise zahl">{[anzahl(vorschlag.anzahl, "Buch", "Bücher"), vorschlag.autor].filter(Boolean).join(", ")}</span></div>
  <div class="wege">
    {#each vorschlag.wege as weg, n (n)}<Chip text={weg} symbol={wegSymbol(weg)} />{/each}
    {#if ki}<Chip text={ki} symbol="robot" />{/if}
  </div>
  <div class="vorschlagsumschlaege">
    {#each reihe.gezeigt as buch (buch.id)}<Umschlag {buch} />{/each}
    {#if reihe.rest}<span class="vorschlagsrest zahl">+{reihe.rest}</span>{/if}
  </div>
  <div class="reihe">
    <Knopf text="Anlegen" symbol="check" haupt klein laeuft={arbeitet} onclick={() => void vorschlaege.anlegen(vorschlag)} />
    <Knopf text="Bücher anpassen" symbol="right-left" klein gesperrt={arbeitet} onclick={onanpassen} />
    <span class="schiebt"><Knopf text="Verwerfen" symbol="xmark" klein frei gesperrt={arbeitet} onclick={() => void vorschlaege.verwerfen(vorschlag)} /></span>
  </div>
</div>
