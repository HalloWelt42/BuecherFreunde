<script lang="ts">
  let { anteil, gut = false, name = undefined }: { anteil: number; gut?: boolean; name?: string } = $props();
  let prozent = $derived(Math.round(Math.min(1, Math.max(0, anteil || 0)) * 100));
</script>

<div class="balken" class:gut role={name ? "progressbar" : undefined} aria-label={name} aria-valuenow={name ? prozent : undefined} aria-valuemin={name ? 0 : undefined} aria-valuemax={name ? 100 : undefined}>
  <i style:width="{prozent}%"></i>
</div>
