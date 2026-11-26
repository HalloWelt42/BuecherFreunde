<!-- Eine Seite Text im Kinderleser: die Zeilen genau so, wie lib/kind/seiten.ts sie umbrochen hat, jedes Wort für sich. Dazu auf
     Wunsch die farbigen Silben, die Lesezeile (nur die Zeile hell, an der das Kind liest) und beim Vorlesen das Wort, das gerade
     klingt. Ab der Stufe Schule tragen markierte Wörter ihre Farbe. -->
<script lang="ts">
  import type { Zeile } from "../../lib/kind/seiten";
  import { kernsilben, wortteile } from "../../lib/kind/silben";
  import type { Wort } from "../../lib/kind/typen";

  let {
    zeilen,
    breite,
    silben = false,
    zeile = -1,
    wort = -1,
    anfang = -1,
    markiert = () => false,
    ontippe,
  }: {
    zeilen: Zeile[];
    /** Breite der Zeilen in Pixeln, wie umbrochen */
    breite: number;
    silben?: boolean;
    /** Die Lesezeile; -1: keine */
    zeile?: number;
    /** Anfang des Wortes, das gerade klingt; -1: keins */
    wort?: number;
    /** Anfang einer Markierung, die gerade entsteht */
    anfang?: number;
    markiert?: (w: Wort) => boolean;
    ontippe?: (zeile: number, wort: Wort | null) => void;
  } = $props();

  function getippt(e: MouseEvent) {
    const z = (e.target as Element).closest<HTMLElement>("[data-zeile]");
    if (!z || !ontippe) return;
    const nr = Number(z.dataset.zeile);
    const w = (e.target as Element).closest<HTMLElement>("[data-wort]");
    ontippe(nr, w ? (zeilen[nr]?.woerter[Number(w.dataset.wort)] ?? null) : null);
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="k-lesetext" class:mit-zeile={zeile >= 0} style:--k-textbreite="{breite}px" onclick={getippt}>
  {#each zeilen as z, i (i)}
    <span class="k-zeile" class:titel={z.art === "titel"} class:neu={z.neuerAbsatz && i > 0} class:hier={i === zeile} data-zeile={i}>
      {#each z.woerter as w, j (w.von)}{#if j > 0}{" "}{/if}<span class="k-w" class:jetzt={w.von === wort} class:anfang={w.von === anfang} class:markiert={markiert(w)} data-wort={j}>{#if silben}{@const t = wortteile(w.text)}{t.vor}{#each kernsilben(t.kern) as s, k (k)}<span class="s{(k % 2) + 1}">{s}</span>{/each}{t.nach}{:else}{w.text}{/if}</span>{/each}
    </span>
  {/each}
</div>
