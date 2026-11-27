<script lang="ts">
  // Angaben vergleichen auf der Buchseite (BF-111, Abnahme 2): dieselbe Werkzeugreihe wie beim Bearbeiten, dazu die ISBN im Buch;
  // was hier übernommen wird, steht gleich im Buch
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Angabenfenster from "./Angabenfenster.svelte";
  import { Angabenwerkzeuge } from "./werkzeuge.svelte";
  import Werkzeugreihe from "./Werkzeugreihe.svelte";
  import { buchziel } from "./ziel";

  let { buch, ongeaendert }: { buch: BuchEinzeln; ongeaendert: () => void } = $props();

  // svelte-ignore state_referenced_locally
  const werkzeuge = new Angabenwerkzeuge(buch, buchziel(buch.id, () => ongeaendert()));
</script>

<Karte titel="Angaben vergleichen" symbol="code-compare" breit>
  <Werkzeugreihe {werkzeuge} mitIsbn />
  {#if werkzeuge.nichts}
    <span class="reihe"><span class="leise"><Symbol name="circle-info" /> Im Buch steht keine ISBN.</span><Knopf text="Über Titel und Autor suchen" symbol="magnifying-glass" klein onclick={() => werkzeuge.vergleiche(werkzeuge.standardquelle, "")} /></span>
  {:else}
    <p class="leise">Nichts ändert sich vor dem Übernehmen.</p>
  {/if}
</Karte>

<Angabenfenster {werkzeuge} />
