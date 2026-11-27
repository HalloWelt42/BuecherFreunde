<script lang="ts">
  // ISBN im Buch (BF-111): je ISBN eine Zeile, geordnet nach Stufe, Fundort und Zahl; fremde Bücher unten unter "Andere Bücher",
  // viele davon zugeklappt. Die erste passende ist gewählt. "ISBN übernehmen" setzt nur die Nummer, "Angaben suchen" öffnet den
  // Vergleich zu dieser ISBN.
  import { quellen } from "../../lib/stand/quellen.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Isbnkandidat from "./Isbnkandidat.svelte";
  import { ANDERE_HOECHSTENS, ANDERE_ZUERST, VIELE, anderezeile, fremd, kopfzeile } from "./isbn";
  import type { Angabenwerkzeuge } from "./werkzeuge.svelte";

  let { werkzeuge: w }: { werkzeuge: Angabenwerkzeuge } = $props();

  let alleAnderen = $state(false);
  let eigen = $derived(w.zeilen.filter((z) => !fremd(z.kandidat)));
  let andere = $derived(w.zeilen.filter((z) => fremd(z.kandidat)));
  let sichtbar = $derived(alleAnderen || andere.length <= ANDERE_HOECHSTENS ? andere : andere.slice(0, ANDERE_ZUERST));
  let kurz = $derived(w.zeilen.length > VIELE);
  let gruppe = $derived(`isbn-${w.buch.id}`);
</script>

{#snippet zeile(z: (typeof w.zeilen)[number])}
  <Isbnkandidat zeile={z} buch={w.buch} {gruppe} {kurz} an={w.gewaehlt === z.kandidat.isbn} onwahl={() => (w.gewaehlt = z.kandidat.isbn)} onpruefe={() => void w.pruefe(z.kandidat.isbn)} />
{/snippet}

<Fenster titel="ISBN im Buch" breite="46rem" onschliessen={() => w.schliesse()}>
  {#if w.suche}<div class="isbnkopf"><span class="leise zahl">{kopfzeile(w.suche)}</span></div>{/if}
  {#if eigen.length}<div class="kandidaten">{#each eigen as z (z.kandidat.isbn)}{@render zeile(z)}{/each}</div>{/if}
  {#if andere.length}
    <div class="kandidaten andere">
      <h3 class="isbngruppe"><Symbol name="book" />Andere Bücher <span class="leise zahl">{anderezeile(andere.map((z) => z.kandidat))}</span></h3>
      {#each sichtbar as z (z.kandidat.isbn)}{@render zeile(z)}{/each}
      {#if sichtbar.length < andere.length}<div class="reihe"><Knopf text="{andere.length - sichtbar.length} weitere zeigen" symbol="chevron-down" klein frei aufgeklappt={false} onclick={() => (alleAnderen = true)} /></div>{/if}
    </div>
  {/if}
  {#snippet fuss()}
    <div class="fensterfuss">
      <span class="tasten2">
        <Knopf text="ISBN übernehmen" symbol="check" gesperrt={!w.gewaehlt} titel={w.ziel.sofort ? "Die Nummer ins Buch eintragen" : "Nur die Nummer ins Feld setzen"} onclick={() => void w.isbnUebernehmen()} />
        <Knopf text="Angaben suchen" symbol="magnifying-glass" haupt gesperrt={!w.gewaehlt || !quellen.buecher.length} titel="Angaben zu dieser ISBN suchen und vergleichen" onclick={() => w.vergleiche(w.standardquelle, w.gewaehlt, w.kandidat)} />
      </span>
    </div>
  {/snippet}
</Fenster>
