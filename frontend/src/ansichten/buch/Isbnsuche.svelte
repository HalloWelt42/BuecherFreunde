<script lang="ts">
  // Das Feld ISBN beim Bearbeiten mit "Im Buch suchen" (BF-111): sucht im ganzen Buch und öffnet die Kandidaten im Fenster. Steht
  // keine ISBN im Buch, sagt es das Feld in einem Satz, daneben der Weg über Titel und Autor. Hat der Lauf "ISBN" Vorschläge
  // gemacht, stehen sie hier zur Wahl (Abnahme 5).
  import { untrack } from "svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { FUNDORTE, STUFEN } from "./isbn";
  import { stellenort } from "./stelle";
  import type { Angabenwerkzeuge } from "./werkzeuge.svelte";

  let { werkzeuge: w, wert, eingesetzt = false, onwert }: { werkzeuge: Angabenwerkzeuge; wert: string; eingesetzt?: boolean; onwert: (isbn: string) => void } = $props();

  let vorschlag = $derived(wert.trim() ? null : (w.zurWahl[0] ?? null));
  let stelle = $derived(vorschlag?.stellen[0] ?? null);

  // einmal beim Öffnen, solange das Buch keine ISBN hat
  $effect(() => untrack(() => {
    if (!wert.trim()) void w.ladeZurWahl();
  }));
</script>

<div class="feld" class:eingesetzt>
  <label for="isbn">ISBN</label>
  <span class="zeile-isbn">
    <input id="isbn" value={wert} oninput={(e) => onwert(e.currentTarget.value)} />
    <Knopf text="Im Buch suchen" symbol="barcode" titel="ISBN im Buch suchen" laeuft={w.sucht} onclick={() => void w.sucheIsbn()} />
  </span>
  {#if w.nichts}
    <span class="reihe"><span class="leise"><Symbol name="circle-info" /> Im Buch steht keine ISBN.</span><Knopf text="Über Titel und Autor suchen" symbol="magnifying-glass" klein onclick={() => w.vergleiche(w.standardquelle, "")} /></span>
  {:else if vorschlag}
    <span class="reihe">
      <span class="leise"><Symbol name="barcode" /> Zur Wahl: <span class="zahl">{vorschlag.isbn}</span>{#if stelle}, {FUNDORTE[stelle.fundort]}, {stellenort(w.buch, stelle)}{/if}, <span class="marke-text {STUFEN[(vorschlag.quelle ?? vorschlag.text).stufe].klasse}">{STUFEN[(vorschlag.quelle ?? vorschlag.text).stufe].wort}</span></span>
      <Knopf text="Ansehen" symbol="list-check" klein titel="Alle ISBN im Buch ansehen und wählen" laeuft={w.sucht} onclick={() => void w.sucheIsbn()} />
    </span>
  {/if}
</div>

<style>
  .zeile-isbn {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .zeile-isbn input {
    flex: 1 1 10rem;
  }
</style>
