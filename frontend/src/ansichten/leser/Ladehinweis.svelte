<script lang="ts">
  // Wartet der Leser lange oder scheitert er, gibt es die Datei auch direkt
  import { alsAnhang } from "../../lib/api/books";
  import type { Ladefehler } from "../../lib/leser/ladefehler";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  let { fehler, adresse, name, onerneut }: { fehler: Ladefehler | null; adresse: string; name: string; onerneut: () => void } = $props();

  const GEDULD_MS = 4000;
  let langsam = $state(false);
  $effect(() => {
    const uhr = setTimeout(() => (langsam = true), GEDULD_MS);
    return () => clearTimeout(uhr);
  });
</script>

<div class="lesehinweis">
  <Zustand art={fehler ? "fehler" : "laedt"} text={fehler?.text ?? (langsam ? "Das dauert länger. Die Datei lässt sich auch direkt öffnen." : "Buch wird geladen")} onerneut={fehler ? onerneut : undefined}>
    {#if fehler ? fehler.dateiDa : langsam}
      <Knopf text="Im Browser öffnen" symbol="up-right-from-square" klein extern href={adresse} />
      <Knopf text="Herunterladen" symbol="download" klein href={alsAnhang(adresse)} download={name} />
    {/if}
  </Zustand>
</div>
