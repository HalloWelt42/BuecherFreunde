<script lang="ts">
  import Symbol from "./Symbol.svelte";
  let { name, werte, wert, gesperrt = false, klein = false, onwahl }: { name: string; werte: [string, string][]; wert: string; gesperrt?: boolean; klein?: boolean; onwahl: (w: string) => void } = $props();
</script>

<span class="auswahl" class:klein>
  <select aria-label={name} disabled={gesperrt} value={wert} onchange={(e) => onwahl(e.currentTarget.value)}>
    {#each werte as [w, text] (w)}<option value={w}>{text}</option>{/each}
  </select>
  <Symbol name="chevron-down" />
</span>
