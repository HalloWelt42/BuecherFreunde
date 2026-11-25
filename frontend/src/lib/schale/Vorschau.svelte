<script lang="ts">
  // Rechts: das gewählte Buch mit den häufigsten Griffen
  import { dateiUrl } from "../api/books";
  import { ladeAblage } from "../api/orte";
  import { formatName, groesse, zahl } from "../format";
  import { leseAdresse, leseKnopf, lesestand, standText } from "../lesestand";
  import { merkmale } from "../stand/merkmale.svelte";
  import { verbindungen } from "../stand/verbindungen.svelte";
  import { wahl } from "../stand/wahl.svelte";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Merkmalsknoepfe from "../teile/Merkmalsknoepfe.svelte";
  import Sterne from "../teile/Sterne.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Umschlag from "../teile/Umschlag.svelte";
  import type { Ablage } from "../typen";

  let buch = $derived(wahl.buch);
  let stand = $derived(buch ? lesestand(buch) : null);
  let ablage = $state<Ablage | null>(null);

  $effect(() => {
    const id = buch?.id;
    ablage = null;
    if (!id) return;
    let gilt = true;
    ladeAblage(id).then((a) => gilt && (ablage = a)).catch(() => {});
    return () => (gilt = false);
  });
</script>

<aside class="vorschau glas milch" aria-label="Vorschau">
  <div class="rollen">
    {#if buch && stand}
      <div class="bild"><Umschlag {buch} sofort /></div>
      <div><h2>{buch.title}</h2><p class="leise">{[buch.author, buch.year].filter(Boolean).join(", ")}</p></div>
      <div class="knopfreihe">
        <Knopf text={leseKnopf(buch)} symbol="book-open" haupt klasse="voll" href={leseAdresse(buch.id)} />
        <Knopf text="Buchseite" symbol="up-right-and-down-left-from-center" href="/book/{buch.id}" />
        <Knopf text="Herunterladen" symbol="download" href={dateiUrl(buch.id)} download={buch.title} />
      </div>
      {#if stand.angefangen}<div><Balken anteil={stand.anteil} name="Lesestand" /><p class="leise zahl">{standText(buch)}</p></div>{/if}
      <div class="reihe">
        <Merkmalsknoepfe {buch} />
        <span class="schiebt"><Sterne wert={buch.rating} onwahl={(n) => void merkmale.sterne(buch, n)} /></span>
      </div>
      <dl class="angaben">
        {#if buch.categories.length}<dt>Regal</dt><dd>{buch.categories.map((c) => c.name).join(", ")}</dd>{/if}
        {#if buch.sammlung}<dt>Sammlung</dt><dd>{buch.sammlung.name}{buch.band_nummer ? `, Band ${buch.band_nummer}` : ""}</dd>{/if}
        <dt>Format</dt><dd>{formatName(buch.file_format)}, {groesse(buch.file_size)}</dd>
        {#if buch.page_count}<dt>Seiten</dt><dd class="zahl">{zahl(buch.page_count)}</dd>{/if}
        {#if ablage?.wolke}<dt>Liegt in</dt><dd>Kellerwolke, {ablage.wolke.pfad}</dd>{/if}
      </dl>
      {#if ablage?.wissen || verbindungen.assistent}
        <div class="platte karte">
          <h2><Symbol name="brain" />Wissen</h2>
          {#if ablage?.wissen}<p class="klein">{ablage.wissen.text}</p>{/if}
          {#if verbindungen.assistent}<Knopf text="Im Assistenten fragen" symbol="comments" klein extern href={verbindungen.frageAdresse(buch.title)} />{/if}
        </div>
      {/if}
    {:else}
      <p class="leise">Ein Buch antippen, dann steht es hier.</p>
    {/if}
  </div>
</aside>
