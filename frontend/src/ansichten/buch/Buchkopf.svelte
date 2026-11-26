<script lang="ts">
  import { datum, formatName, groesse, sprache, tagWort, zahl } from "../../lib/format";
  import { leseKnopf, lesestand, leseweise, schriftprobe, standText } from "../../lib/lesestand";
  import { arten } from "../../lib/stand/arten.svelte";
  import { merkmale } from "../../lib/stand/merkmale.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Merkmalsknoepfe from "../../lib/teile/Merkmalsknoepfe.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Sterne from "../../lib/teile/Sterne.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import type { BuchEinzeln, Umschlagart } from "../../lib/typen";
  import Fassungslabels from "./Fassungslabels.svelte";
  import { fassungsAdresse, type Buchfassungen } from "./fassungen.svelte";
  import Kategoriechips from "./Kategoriechips.svelte";
  import Regalchips from "./Regalchips.svelte";
  import { buchLoeschen } from "./loeschen";

  let { buch, fassungen, onneu, ongeaendert }: { buch: BuchEinzeln; fassungen: Buchfassungen; onneu: (neu: Partial<BuchEinzeln>) => void; ongeaendert: () => void } = $props();

  // "Lesen" öffnet die gewählte Fassung (BF-71); eine Übersetzung hat ihren eigenen Lesestand
  let uebersetzung = $derived(fassungen.uebersetzung);
  let gelesen = $derived(uebersetzung ? { reading_position: fassungen.lesestand?.position ?? "", page_count: 0, last_read_at: fassungen.lesestand?.gelesen_am ?? null } : buch);
  let stand = $derived(lesestand(gelesen));
  let probe = $derived(schriftprobe(gelesen.reading_position));
  let standzeile = $derived([standText(gelesen), gelesen.last_read_at ? `zuletzt ${tagWort(gelesen.last_read_at)}` : "", ...leseweise(gelesen.reading_position)].filter(Boolean).join(", "));
  let lesesprache = $derived(uebersetzung?.sprache ?? null);
  // Vor dem Zerlegen gibt es noch nichts zu lesen
  let lesbar = $derived(!uebersetzung || !!uebersetzung.kapitel_gesamt);

  const UMSCHLAEGE: [Umschlagart, string][] = [["gestaltet", "Gestaltet"], ["titelseite", "Titelseite"]];
  let waehlt = $state(false);
  // Die Wahl gibt es, wo die Titelseite fast weiß ist oder schon gewählt wurde (BF-59)
  let mitWahl = $derived(buch.umschlag_schlicht || !!buch.umschlag_wahl);

  let angaben = $derived(
    ([
      ["Art", arten.typName(buch.typ)],
      ["Gattung", buch.gattung ? arten.gattungName(buch.gattung) : ""],
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

  async function waehleUmschlag(art: Umschlagart) {
    if (art === buch.umschlag) return;
    waehlt = true;
    onneu(await merkmale.umschlag(buch, art));
    waehlt = false;
  }
</script>

<section class="buchkopf platte">
  <div>
    <Umschlag {buch} sofort />
    {#if mitWahl}<div class="umschlagwahl"><Segment name="Umschlag" werte={UMSCHLAEGE} wert={buch.umschlag} gesperrt={waehlt} onwahl={(w) => void waehleUmschlag(w)} /></div>{/if}
  </div>
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
      <Fassungslabels {buch} {fassungen} />
      <div class="reihe">
        <Knopf text={leseKnopf(gelesen)} symbol="book-open" haupt href={fassungsAdresse(buch.id, lesesprache)} gesperrt={!lesbar} titel={lesbar ? undefined : "Gleich gibt es die ersten Kapitel"} />
        <Knopf text="Von vorn" symbol="backward-step" href={fassungsAdresse(buch.id, lesesprache, { restart: 1 })} gesperrt={!lesbar} />
      </div>
      {#if uebersetzung}
        <!-- Was zur Übersetzung gehört; der Auftrag, solange sie nicht fertig ist -->
        <div class="reihe gleichtasten">
          {#if uebersetzung.stand !== "fertig"}<Knopf text="Auftrag" symbol="language" href="/book/{buch.id}/uebersetzung" />{/if}
          <Knopf text="Prüfbericht" symbol="list-check" href="/book/{buch.id}/pruefbericht" />
          <Knopf text="Begriffe" symbol="spell-check" href="/book/{buch.id}/begriffe" />
        </div>
      {/if}
      {#if stand.angefangen}
        <div class="stand-zeile">
          <Balken anteil={stand.anteil} name="Lesestand" />
          <p class="leise zahl">{standzeile}</p>
          {#if probe}<p class="probe" style:font-family={probe.schrift} style:color={probe.farbe || undefined} style:background={probe.grund || undefined} title="Schriftprobe">{probe.name}</p>{/if}
        </div>
      {/if}
      <Kategoriechips {buch} {ongeaendert} />
      <Regalchips {buch} {ongeaendert} />
    </div>
    <div class="rechts">
      {#if buch.description}<p class="zitat beschreibung">{buch.description}</p>{/if}
      <dl class="angaben">{#each angaben as [feld, wert] (feld)}<dt>{feld}</dt><dd class="zahl">{wert}</dd>{/each}</dl>
    </div>
  </div>
</section>

<style>
  .umschlagwahl {
    margin-top: 0.5rem;
    display: flex;
    justify-content: center;
  }
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
