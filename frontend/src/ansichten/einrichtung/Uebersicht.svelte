<script lang="ts">
  // Abschluss von "Neu beginnen": was eingerichtet und was übersprungen ist, jede Zeile mit dem Weg in ihre Einstellung. Ein
  // Weg dorthin schließt die Ersteinrichtung ab, wie "Zur Bibliothek".
  import { ladeAnschluesse, type Anschluss } from "../../lib/api/einrichtung";
  import { uebersicht } from "../../lib/einrichtung/ablauf";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let anschluesse = $state<Anschluss[]>([]);

  $effect(() => {
    ladeAnschluesse().then((a) => (anschluesse = a)).catch(() => {});
  });

  let liste = $derived(uebersicht(einrichtung.schritte, anschluesse));

  function gehe(e: MouseEvent, ziel: string) {
    e.preventDefault();
    void einrichtung.tu(() => einrichtung.abschliessen(ziel), "Nicht abgeschlossen");
  }
</script>

{#snippet zeile(z: (typeof liste.eingerichtet)[number], stand: "gut" | "aus")}
  <div class="stelle zeile-stand" class:ohne-ziel={!z.ziel}>
    <span class="led {stand}"></span>
    <span><b>{z.name}</b><br /><span class="leise">{z.text}</span></span>
    {#if z.ziel}
      {@const [name, weg] = z.ziel}
      <Knopf text={name} symbol="arrow-right" klein frei href={weg} klasse="ew-ziel" titel="Einstellungen, {name}" onclick={(e) => gehe(e, weg)} />
    {/if}
  </div>
{/snippet}

<Schrittrahmen weiter={{ text: "Zur Bibliothek", symbol: "book-bookmark", tun: () => einrichtung.abschliessen() }}>
  <p class="klein">Alles lässt sich in den Einstellungen ändern.</p>
  <div class="ew-uebersicht">
    <h3 class="ew-gruppe-kopf"><Symbol name="circle-check" />Eingerichtet <span class="leise zahl">{liste.eingerichtet.length}</span></h3>
    {#each liste.eingerichtet as z (z.schluessel)}{@render zeile(z, "gut")}{/each}
    {#if liste.uebersprungen.length}
      <h3 class="ew-gruppe-kopf"><Symbol name="forward" />Übersprungen <span class="leise zahl">{liste.uebersprungen.length}</span></h3>
      {#each liste.uebersprungen as z (z.schluessel)}{@render zeile(z, "aus")}{/each}
    {/if}
  </div>
</Schrittrahmen>
