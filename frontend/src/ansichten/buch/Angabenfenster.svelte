<script lang="ts">
  // Das Fenster, das ein Werkzeug für die Angaben gerade offen hat; immer nur eines zugleich
  import Beschreibungstext from "./Beschreibungstext.svelte";
  import Isbnfenster from "./Isbnfenster.svelte";
  import Kivorschlag from "./Kivorschlag.svelte";
  import Vergleichsfenster from "./Vergleichsfenster.svelte";
  import type { Angabenwerkzeuge } from "./werkzeuge.svelte";

  let { werkzeuge: w }: { werkzeuge: Angabenwerkzeuge } = $props();
  let f = $derived(w.fenster);
</script>

{#if f?.art === "vergleich"}
  {#key f}<Vergleichsfenster werkzeuge={w} quelle={f.quelle} isbn={f.isbn} kandidat={f.kandidat} />{/key}
{:else if f?.art === "isbn"}
  <Isbnfenster werkzeuge={w} />
{:else if f?.art === "buchtext"}
  <Beschreibungstext buchId={w.buch.id} ziel={w.ziel} onschliessen={() => w.schliesse()} />
{:else if f?.art === "ki"}
  <Kivorschlag buchId={w.buch.id} ziel={w.ziel} onschliessen={() => w.schliesse()} />
{/if}
