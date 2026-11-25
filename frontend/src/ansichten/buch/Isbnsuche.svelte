<script lang="ts">
  import { isbnScan } from "../../lib/api/books";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { BuchEinzeln } from "../../lib/typen";

  let { buch, wert, onwert }: { buch: BuchEinzeln; wert: string; onwert: (isbn: string) => void } = $props();
  let sucht = $state(false);
  let funde = $state<[string, string][] | null>(null);

  async function suche() {
    sucht = true;
    try {
      const { gefunden } = await isbnScan(buch.id);
      funde = (gefunden as { isbn13?: string; isbn10?: string }[]).flatMap((f) => ([["ISBN-13", f.isbn13], ["ISBN-10", f.isbn10]] as [string, string | undefined][]).filter((x): x is [string, string] => !!x[1]));
    } catch (e) {
      melde.schlecht(e, "ISBN nicht gesucht");
    } finally {
      sucht = false;
    }
  }
</script>

<div class="feld">
  <label for="isbn">ISBN</label>
  <span class="zeile-isbn">
    <input id="isbn" value={wert} oninput={(e) => onwert(e.currentTarget.value)} />
    <Knopf text="Im Text suchen" symbol="barcode" laeuft={sucht} onclick={suche} />
  </span>
  {#if funde}
    <span class="reihe">
      {#each funde as [art, isbn] (isbn)}<Chip text="{art}: {isbn}" titel="Übernehmen" onclick={() => { onwert(isbn); funde = null; }} />{:else}<span class="leise">Im Buchtext steht keine ISBN.</span>{/each}
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
