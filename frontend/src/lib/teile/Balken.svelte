<script lang="ts">
  // Fortschritt als Balken; `unbestimmt`, solange sich kein Ende absehen lässt (etwa beim Warten auf einen Dienst, BF-98)
  let { anteil = 0, gut = false, unbestimmt = false, name = undefined }: { anteil?: number; gut?: boolean; unbestimmt?: boolean; name?: string } = $props();
  let prozent = $derived(Math.round(Math.min(1, Math.max(0, anteil || 0)) * 100));
  let mitWert = $derived(!!name && !unbestimmt);
</script>

<div class="balken" class:gut class:unbestimmt role={name ? "progressbar" : undefined} aria-label={name} aria-valuenow={mitWert ? prozent : undefined} aria-valuemin={mitWert ? 0 : undefined} aria-valuemax={mitWert ? 100 : undefined}>
  <i style:width={unbestimmt ? undefined : `${prozent}%`}></i>
</div>
