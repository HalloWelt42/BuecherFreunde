<script lang="ts">
  import type { Snippet } from "svelte";
  let { text = "", an, gesperrt = false, name = undefined, onwahl, children = undefined }: { text?: string; an: boolean; gesperrt?: boolean; name?: string; onwahl: (an: boolean) => void; children?: Snippet } = $props();
</script>

<label class="haekchen" class:gesperrt>
  <input type="checkbox" checked={an} disabled={gesperrt} aria-label={name} onchange={(e) => onwahl(e.currentTarget.checked)} />
  {#if text || children}<span>{text}{@render children?.()}</span>{/if}
</label>
