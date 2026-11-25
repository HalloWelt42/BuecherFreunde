<script lang="ts">
  // Auswahl aus einer Liste, auf Wunsch in Gruppen
  import Symbol from "./Symbol.svelte";
  type Wert = [string, string];
  interface Eigenschaften {
    name: string;
    werte?: Wert[];
    gruppen?: [string, Wert[]][];
    wert: string;
    gesperrt?: boolean;
    klein?: boolean;
    onwahl: (w: string) => void;
  }
  let { name, werte = [], gruppen = [], wert, gesperrt = false, klein = false, onwahl }: Eigenschaften = $props();
</script>

{#snippet punkte(liste: Wert[])}{#each liste as [w, text] (w)}<option value={w}>{text}</option>{/each}{/snippet}

<span class="auswahl" class:klein>
  <select aria-label={name} disabled={gesperrt} value={wert} onchange={(e) => onwahl(e.currentTarget.value)}>
    {@render punkte(werte)}
    {#each gruppen as [titel, liste] (titel)}<optgroup label={titel}>{@render punkte(liste)}</optgroup>{/each}
  </select>
  <Symbol name="chevron-down" />
</span>
