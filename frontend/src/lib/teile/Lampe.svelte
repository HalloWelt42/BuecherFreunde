<script lang="ts">
  import type { Guete } from "../typen";
  let { stand, text, titel = undefined }: { stand: Guete | "aus"; text: string; titel?: string } = $props();
</script>

<span class="lampe" title={titel}><span class="led {stand}"></span>{text}</span>
