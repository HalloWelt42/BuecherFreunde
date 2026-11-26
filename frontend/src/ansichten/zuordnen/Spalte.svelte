<script lang="ts">
  // Eine Spalte der Zuordnung (BF-67): Überschrift, Werkzeuge, Bücher zum Anhaken und Ziehen, Ablage
  import type { Snippet } from "svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Buchzeile from "../../lib/teile/Buchzeile.svelte";
  import Nachlader from "../../lib/teile/Nachlader.svelte";
  import { bandText, kurztitel } from "../sammlung/angaben";
  import { ziehen } from "./ziehen.svelte";
  import type { Spalte, Zuordnung } from "./zuordnung.svelte";

  interface Eigenschaften {
    zuordnung: Zuordnung;
    spalte: Spalte;
    titel: string;
    /** Leise neben der Überschrift: eine Zahl oder was gezeigt wird */
    zusatz: string;
    /** Name und Kopf der Reihe: links dann "Band N" und der Titel ohne sie */
    reihe?: string[];
    leer: string;
    children?: Snippet;
  }
  let { zuordnung, spalte, titel, zusatz, reihe = undefined, leer, children = undefined }: Eigenschaften = $props();

  let seiten = $derived(spalte === "drin" ? zuordnung.drin : zuordnung.uebrig);
  let buecher = $derived(zuordnung.liste(spalte));
  let ziehbar = $derived(!schale.telefon);
  let nimmt = $derived(ziehen.von !== null && zuordnung.nimmt(ziehen.von, spalte));
  let hier = $derived(ziehen.ueber?.spalte === spalte ? ziehen.ueber : null);
  /** Nur wo es eine Reihenfolge gibt, zählt die Stelle zwischen den Zeilen */
  let mitStelle = $derived(spalte === "drin" && !!zuordnung.ziel.ordne);

  /** Vor welchem Buch das Gezogene landet: obere Hälfte einer Zeile davor, untere danach */
  function stelle(e: DragEvent): number | null {
    if (!mitStelle) return null;
    const zeile = (e.target as Element | null)?.closest<HTMLElement>("[data-buch]");
    if (!zeile) return null;
    const r = zeile.getBoundingClientRect();
    if (e.clientY < r.top + r.height / 2) return Number(zeile.dataset.buch);
    const naechste = zeile.nextElementSibling as HTMLElement | null;
    return naechste?.dataset.buch ? Number(naechste.dataset.buch) : null;
  }

  function ueber(e: DragEvent) {
    if (!nimmt) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    ziehen.ueber = { spalte, vor: stelle(e) };
  }

  function verlaesst(e: DragEvent) {
    const nach = e.relatedTarget as Node | null;
    if (hier && !(nach && (e.currentTarget as HTMLElement).contains(nach))) ziehen.ueber = null;
  }

  function lege(e: DragEvent) {
    if (!nimmt || !ziehen.von) return;
    e.preventDefault();
    const [von, ids, vor] = [ziehen.von, [...ziehen.ids], stelle(e)];
    ziehen.ende();
    void zuordnung.lege(von, spalte, ids, vor);
  }

  const zeilentitel = (titelGanz: string, band: string) => (reihe === undefined ? titelGanz : kurztitel(titelGanz, reihe, band));
</script>

<section class="zuordnungsspalte platte" class:nimmt aria-label={titel} ondragover={ueber} ondragleave={verlaesst} ondrop={lege}>
  <h3>{titel} <span class="leise zahl">{zusatz}</span></h3>
  {@render children?.()}
  <div class="zuordnungszeilen rollen">
    {#each buecher as buch (buch.id)}
      <Buchzeile {buch} titel={zeilentitel(buch.title, buch.band_nummer)} band={reihe === undefined ? "" : bandText(buch.band_nummer)} an={zuordnung.hat(spalte, buch.id)} onwahl={(an) => zuordnung.hakeAn(spalte, buch.id, an)}
        {ziehbar} gezogen={ziehen.zieht(buch.id)} davor={mitStelle && hier?.vor === buch.id} ondragstart={(e) => ziehen.beginne(e, spalte, zuordnung.gezogene(spalte, buch.id))} ondragend={() => ziehen.ende()} />
    {:else}
      {#if seiten.fehler}<p class="marke-text schlecht" role="alert">{seiten.fehler}</p>
      {:else if seiten.geladen && !seiten.laedt}<p class="leise">{leer}</p>
      {:else}<p class="leise">Wird geladen</p>{/if}
    {/each}
    {#if !seiten.ganz && buecher.length}<Nachlader geladen={seiten.liste.length} gesamt={seiten.gesamt} laedt={seiten.laedt} onmehr={() => void seiten.mehr()} />{/if}
  </div>
  {#if ziehbar && (spalte === "drin" || nimmt)}<div class="ablagestelle" class:an={hier !== null && hier.vor === null}>hierher ziehen</div>{/if}
</section>
