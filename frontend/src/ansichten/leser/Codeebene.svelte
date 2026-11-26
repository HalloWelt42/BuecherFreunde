<script lang="ts">
  // Ebene der Codestellen über einer PDF-Seite (BF-29): Rechtecke aus dem Server (Punkte der Seite, oben links) mal Maß der
  // Anzeige. Die Taste sitzt auf der oberen Kante des ersten Teils, rechts, damit sie nie den Kastentitel deckt; jeder
  // weitere Teil trägt die Marke der Fortsetzung. Ist das Listing im Fenster offen, markiert ein Streifen links alle Teile.
  import type { Codestelle } from "../../lib/api/ausfuehren";
  import { ausfuehren } from "../../lib/stand/ausfuehren.svelte";
  import Codetaste from "./Codetaste.svelte";

  let { buch, nr, stellen, mass, seitenname, onoeffne }: { buch: number; nr: number; stellen: Codestelle[]; mass: number; seitenname: (nr: number) => string; onoeffne: (s: Codestelle) => void } = $props();
</script>

{#each stellen as s (s.kennung)}
  {#each s.teile as t, k (k)}
    {#if t.seite === nr && t.rechteck}
      {@const [x0, y0, x1, y1] = t.rechteck}
      <div class="codestelle" class:offen={ausfuehren.istOffen(buch, s.kennung)} class:oben-offen={t.offen_oben} class:unten-offen={t.offen_unten} style:--x0={x0} style:--y0={y0} style:--x1={x1} style:--y1={y1} style:--mass={mass}>
        <Codetaste stelle={s} weiterVon={k > 0 ? seitenname(s.teile[0].seite ?? nr) : ""} onoeffne={() => onoeffne(s)} />
      </div>
    {/if}
  {/each}
{/each}
