<script lang="ts">
  // Eine Sicherung zum Wählen: Name, Datum, Größe, Bücher und Profile; die neueste trägt eine Marke
  import type { Sicherung } from "../../lib/api/einrichtung";
  import { sicherungszeile } from "../../lib/einrichtung/saetze";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { sicherung, gewaehlt, neueste = false, onwahl }: { sicherung: Sicherung; gewaehlt: boolean; neueste?: boolean; onwahl: () => void } = $props();
</script>

<button type="button" class="stelle zeile-stand ew-waehlbar" aria-pressed={gewaehlt} onclick={onwahl}>
  <span class="marke" class:an={gewaehlt}><Symbol name="check" /></span>
  <span><b class="dateiname">{sicherung.name}</b><br /><span class="leise zahl">{sicherungszeile(sicherung)}</span></span>
  {#if neueste}<span class="katalogmarke">Neueste</span>{:else}<span></span>{/if}
</button>
