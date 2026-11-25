<script lang="ts">
  import { tick } from "svelte";
  import { route } from "../../lib/router.svelte.js";
  import Chip from "../../lib/teile/Chip.svelte";
  import Darstellungsreiter from "./Darstellungsreiter.svelte";
  import Mehrreiter from "./Mehrreiter.svelte";
  import Regalreiter from "./Regalreiter.svelte";
  import Verbindungsreiter from "./Verbindungsreiter.svelte";
  import Wartungsreiter from "./Wartungsreiter.svelte";
  import { reiter, reiterAus } from "./reiter";

  let hier = $derived(reiterAus(route.path));
  let flaeche: HTMLElement | undefined = $state();

  // Alte Adressen meinen eine Stelle im Reiter, neue den Anfang. Bis die Karten darüber geladen sind, rutscht der Inhalt
  // noch; die Stelle bleibt oben, bis jemand selbst rollt.
  const FESTHALTEN_MS = 4000;

  $effect(() => {
    const { reiter: jetzt, stelle } = hier;
    const f = flaeche;
    if (!f || !jetzt) return;
    if (!stelle) {
      void tick().then(() => (f.scrollTop = 0));
      return;
    }
    const rolle = () => f.querySelector(`#${stelle}`)?.scrollIntoView({ block: "start" });
    const waechter = new ResizeObserver(rolle);
    const fertig = () => waechter.disconnect();
    void tick().then(() => {
      rolle();
      if (f.firstElementChild) waechter.observe(f.firstElementChild);
    });
    const uhr = setTimeout(fertig, FESTHALTEN_MS);
    for (const e of ["wheel", "touchstart", "keydown", "pointerdown"]) f.addEventListener(e, fertig, { once: true, passive: true });
    return () => {
      clearTimeout(uhr);
      fertig();
    };
  });
</script>

<div class="werkzeug">
  <h1>Einstellungen</h1>
  <nav class="reihe reiterzeile" aria-label="Bereiche der Einstellungen">
    {#each reiter as [schluessel, text, symbol] (schluessel)}
      <Chip {text} {symbol} href="/settings/{schluessel}" gedrueckt={hier.reiter === schluessel} />
    {/each}
  </nav>
</div>

<div class="inhalt rollen" bind:this={flaeche}>
  <div class="raster">
    {#if hier.reiter === "darstellung"}<Darstellungsreiter />
    {:else if hier.reiter === "verbindungen"}<Verbindungsreiter />
    {:else if hier.reiter === "regale"}<Regalreiter />
    {:else if hier.reiter === "wartung"}<Wartungsreiter />
    {:else}<Mehrreiter />{/if}
  </div>
</div>
