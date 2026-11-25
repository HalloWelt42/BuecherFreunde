<script lang="ts">
  let { name, wert, von, bis, schritt = 1, anzeige = String(wert), onwahl }: { name: string; wert: number; von: number; bis: number; schritt?: number; anzeige?: string; onwahl: (w: number) => void } = $props();
</script>

<label class="regler">
  <span class="regler-kopf"><span>{name}</span><span class="zahl">{anzeige}</span></span>
  <input type="range" min={von} max={bis} step={schritt} value={wert} style:--anteil="{((wert - von) / (bis - von)) * 100}%" oninput={(e) => onwahl(Number(e.currentTarget.value))} />
</label>
