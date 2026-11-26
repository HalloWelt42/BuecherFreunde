<script lang="ts">
  import { datum, formatName, groesse, sprache, tagWort, zahl } from "../../lib/format";
  import { leseAdresse, leseKnopf, lesestand, leseweise, schriftprobe, standText } from "../../lib/lesestand";
  import { merkmale } from "../../lib/stand/merkmale.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Merkmalsknoepfe from "../../lib/teile/Merkmalsknoepfe.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Regalchips from "./Regalchips.svelte";
  import { buchLoeschen } from "./loeschen";

  let { buch, onneu, ongeaendert }: { buch: BuchEinzeln; onneu: (neu: Partial<BuchEinzeln>) => void; ongeaendert: () => void } = $props();

  let stand = $derived(lesestand(buch));
  let probe = $derived(schriftprobe(buch.reading_position));
  let standzeile = $derived([standText(buch), buch.last_read_at ? `zuletzt ${tagWort(buch.last_read_at)}` : "", ...leseweise(buch.reading_position)].filter(Boolean).join(", "));

  let angaben = $derived(
    ([
      ["Format", `${formatName(buch.file_format)}, ${groesse(buch.file_size)}`],
      ["Seiten", buch.page_count ? zahl(buch.page_count) : ""],
      ["ISBN", buch.isbn],
      ["Sprache", sprache(buch.language)],
      ["Verlag", buch.publisher],
      ["Jahr", buch.year ? String(buch.year) : ""],
      ["Datei", buch.file_name],
      ["Dazu am", datum(buch.created_at)],
      ["Gelesen", buch.last_read_at ? datum(buch.last_read_at) : ""],
    ] as [string, string][]).filter(([, w]) => w),
  );

  async function bewerte(n: number) {
    onneu(await merkmale.sterne(buch, n));
  }
</script>

<section class="buchkopf platte">
  <div><Umschlag {buch} sofort /></div>
  <div class="zwei">
    <div class="rechts">
      <div>
        <h1>{buch.title}</h1>
        <p>
          {#each buch.authors as a, n (a.id)}{#if n}, {/if}<a class="autor" href="/author/{a.id}">{a.name}</a>{:else}{buch.author}{/each}{#if buch.year}, {buch.year}{/if}
        </p>
      </div>
      <div class="reihe">
        <Sterne wert={buch.rating} onwahl={(n) => void bewerte(n)} /><Merkmalsknoepfe {buch} {onneu} />
        <span class="loeschen"><Knopf text="Buch löschen" symbol="trash" nur onclick={() => void buchLoeschen(buch.id)} /></span>
      </div>
      <div class="reihe">
        <Knopf text={leseKnopf(buch)} symbol="book-open" haupt href={leseAdresse(buch.id)} />
        <Knopf text="Von vorn" symbol="backward-step" href={leseAdresse(buch.id, { restart: 1 })} />
      </div>
      {#if stand.angefangen}
        <div class="stand-zeile">
          <Balken anteil={stand.anteil} name="Lesestand" />
          <p class="leise zahl">{standzeile}</p>
          {#if probe}<p class="probe" style:font-family={probe.schrift} style:color={probe.farbe || undefined} style:background={probe.grund || undefined} title="Schriftprobe">{probe.name}</p>{/if}
        </div>
      {/if}
      <Regalchips {buch} {ongeaendert} />
    </div>
    <div class="rechts">
      {#if buch.description}<p class="zitat beschreibung">{buch.description}</p>{/if}
      <dl class="angaben">{#each angaben as [feld, wert] (feld)}<dt>{feld}</dt><dd class="zahl">{wert}</dd>{/each}</dl>
    </div>
  </div>
</section>

<style>
  /* Abstand, damit man Löschen nicht statt Gelesen trifft; ausgelöst wird ohnehin erst nach der Rückfrage (BF-60) */
  .loeschen {
    margin-left: 0.5rem;
  }
  .autor {
    color: inherit;
    text-decoration-color: var(--linie);
    text-underline-offset: 3px;
  }
  .stand-zeile {
    max-width: 28rem;
    display: grid;
    gap: 0.25rem;
  }
  .probe {
    justify-self: start;
    padding: 0.125rem 0.5rem;
    border-radius: var(--r1);
    font-size: 0.875rem;
    box-shadow: 0 0 0 1px var(--linie);
  }
  .beschreibung {
    white-space: pre-line;
    max-height: 24rem;
    overflow: auto;
  }
</style>
