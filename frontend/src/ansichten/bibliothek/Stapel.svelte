<script lang="ts">
  // Gestapelte Umschläge einer Sammlung mit der Anzahl oben rechts (BF-66)
  import { zahl } from "../../lib/format";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { Sammlungseintrag } from "../../lib/typen";
  import { stapellagen } from "./sammlungseintrag";

  let { sammlung }: { sammlung: Sammlungseintrag } = $props();
  let lagen = $derived(stapellagen(sammlung.umschlaege));
</script>

<span class="umschlagstapel">
  {#if lagen.hinten}<Umschlag buch={lagen.hinten} klasse="hinten" />{/if}
  {#if lagen.mitte}<Umschlag buch={lagen.mitte} klasse="mitte" />{/if}
  {#if lagen.vorn}<Umschlag buch={lagen.vorn} />{:else}<span class="umschlag leer"></span>{/if}
  <span class="anzahl zahl" aria-hidden="true">{zahl(sammlung.anzahl)}</span>
</span>
