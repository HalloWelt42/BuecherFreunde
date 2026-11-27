<script lang="ts">
  // Schritt Anschlüsse: Kellerwolke, Leitstelle, Vertonung und Nachschlag, alles freiwillig
  import { ladeAnschluesse, type Anschluss, type Schritt } from "../../lib/api/einrichtung";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Anschlusskarte from "./Anschlusskarte.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let liste = $state<Anschluss[] | null>(null);
  let fehler = $state("");

  async function lade() {
    try {
      liste = await ladeAnschluesse();
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade());
</script>

<!-- Ohne einen einzigen Anschluss gilt Weiter als übersprungen; so steht es am Ende richtig da -->
<Schrittrahmen ueberspringen={!schritt.pflicht} weiter={{ tun: () => (liste?.some((a) => a.adresse) ? einrichtung.weiter() : einrichtung.ueberspringen()) }}>
  <p class="leise">Alles freiwillig, ohne Anschlüsse läuft die App voll.</p>
  {#if liste}
    {#each liste as a (a.art)}<Anschlusskarte anschluss={a} ongeaendert={lade} />{/each}
  {:else if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
  {:else}
    <Zustand art="laedt" text="Anschlüsse werden geholt" />
  {/if}
</Schrittrahmen>
