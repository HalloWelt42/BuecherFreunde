<script lang="ts">
  // Unten im Feld Darstellung: Voreinstellungen und, eingeklappt, die Feinheiten von Blatt und Satz
  import { BEREICHE, lesehilfen, OHNE, type Blatthilfen, type Voreinstellung } from "../../lib/leser/lesehilfen.svelte";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Stufenregler from "./Stufenregler.svelte";
  /** text: Abstände im Satz wirken (nicht beim PDF als Bild) */
  let { sitzung, text = true }: { sitzung: Lesesitzung; text?: boolean } = $props();

  let offen = $state(false);
  let name = $state("");
  let benennt = $state("");
  let neuerName = $state("");
  let h = $derived(lesehilfen.hilfen);
  let farben = $derived(sitzung.farbwahl?.jetzt());
  const gleich = (a: Blatthilfen, b: Blatthilfen) => (Object.keys(a) as (keyof Blatthilfen)[]).every((k) => a[k] === b[k]);
  let aktiv = $derived(lesehilfen.voreinstellungen.find((v) => farben && v.fg.toLowerCase() === farben.fg.toLowerCase() && v.bg.toLowerCase() === farben.bg.toLowerCase() && gleich(v.hilfen, h)));
  let gemerkt = $derived(lesehilfen.fuerBuch(sitzung.buch.id));
  let eigene = $derived(lesehilfen.voreinstellungen.filter((v) => !v.fest));
  const pz = (w: number) => `${w} %`;

  function waehle(v: Voreinstellung) {
    sitzung.farbwahl?.setze(v.fg, v.bg);
    lesehilfen.setzeHilfen(v.hilfen);
    if (gemerkt) lesehilfen.merkeFuerBuch(sitzung.buch.id, v.name);
  }

  function speichere(e: SubmitEvent) {
    e.preventDefault();
    if (!farben) return;
    if (lesehilfen.speichere(name, farben.fg, farben.bg)) name = "";
  }

  async function loesche(v: Voreinstellung) {
    const n = lesehilfen.buecherMit(v.name);
    const folgen = [`Die Voreinstellung "${v.name}" geht verloren.`, ...(n ? [`${n === 1 ? "Ein Buch merkt" : `${n} Bücher merken`} sie sich; dort gilt dann wieder, was das Gerät vorgibt.`] : [])];
    if (await frage({ titel: "Voreinstellung löschen?", folgen, ja: "Löschen" })) lesehilfen.loesche(v.name);
  }

  function benenne(e: SubmitEvent) {
    e.preventDefault();
    if (lesehilfen.benenne(benennt, neuerName)) benennt = "";
  }
</script>

<div class="feld">
  Voreinstellung
  <div class="tastenraster" style:--spalten="4" role="group" aria-label="Voreinstellung">
    {#each lesehilfen.voreinstellungen as v (v.name)}
      <button type="button" class="chip" style:background={v.bg} style:color={v.fg} aria-pressed={aktiv?.name === v.name} onclick={() => waehle(v)}>{v.name}</button>
    {/each}
  </div>
  <Haekchen text="Für dieses Buch merken" an={!!gemerkt} gesperrt={!aktiv && !gemerkt} onwahl={(an) => lesehilfen.merkeFuerBuch(sitzung.buch.id, an ? (aktiv?.name ?? null) : null)} />
</div>

<Knopf text={offen ? "Weniger" : "Blatt und Satz, eigene Voreinstellungen"} symbol={offen ? "chevron-up" : "sliders"} klein frei aufgeklappt={offen} onclick={() => (offen = !offen)} />
{#if offen}
  <Stufenregler name="Helligkeit" wert={h.helligkeit} bereich={BEREICHE.helligkeit} anzeige={pz(h.helligkeit)} onwahl={(helligkeit) => lesehilfen.setzeHilfen({ helligkeit })} />
  <Stufenregler name="Kontrast" wert={h.kontrast} bereich={BEREICHE.kontrast} anzeige={pz(h.kontrast)} onwahl={(kontrast) => lesehilfen.setzeHilfen({ kontrast })} />
  <Stufenregler name="Wärme" wert={h.waerme} bereich={BEREICHE.waerme} anzeige={pz(h.waerme)} onwahl={(waerme) => lesehilfen.setzeHilfen({ waerme })} />
  <Stufenregler name="Graustufen" wert={h.grau} bereich={BEREICHE.grau} anzeige={pz(h.grau)} onwahl={(grau) => lesehilfen.setzeHilfen({ grau })} />
  {#if text}
    <Stufenregler name="Abbildungen" wert={h.bilder} bereich={BEREICHE.bilder} anzeige={pz(h.bilder)} onwahl={(bilder) => lesehilfen.setzeHilfen({ bilder })} />
    <Stufenregler name="Zeichenabstand" wert={h.zeichen} bereich={BEREICHE.zeichen} anzeige="{(h.zeichen / 100).toLocaleString('de-DE')} em" onwahl={(zeichen) => lesehilfen.setzeHilfen({ zeichen })} />
    <Stufenregler name="Wortabstand" wert={h.woerter} bereich={BEREICHE.woerter} anzeige="{(h.woerter / 100).toLocaleString('de-DE')} em" onwahl={(woerter) => lesehilfen.setzeHilfen({ woerter })} />
    <Stufenregler name="Absatzabstand" wert={h.absatz} bereich={BEREICHE.absatz} anzeige="{(h.absatz / 10).toLocaleString('de-DE')} em" onwahl={(absatz) => lesehilfen.setzeHilfen({ absatz })} />
    <div class="feld">Ausrichtung<Segment name="Ausrichtung" werte={[["links", "Links"], ["block", "Blocksatz"]]} wert={h.ausrichtung} onwahl={(ausrichtung) => lesehilfen.setzeHilfen({ ausrichtung })} /></div>
    <Haekchen text="Silbentrennung" an={h.trennung} onwahl={(trennung) => lesehilfen.setzeHilfen({ trennung })} />
  {/if}
  <Knopf text="Blatt und Satz zurücksetzen" symbol="rotate-left" klein frei gesperrt={gleich(h, OHNE)} onclick={() => lesehilfen.setzeHilfen(OHNE)} />
  <form class="speichern" onsubmit={speichere}>
    <input class="eingabe" placeholder="Name der Voreinstellung" aria-label="Name der Voreinstellung" maxlength="40" bind:value={name} />
    <Knopf text="Speichern" symbol="floppy-disk" klein art="submit" gesperrt={!name.trim() || !farben} titel="Farben, Blatt und Satz, wie sie jetzt sind" />
  </form>
  {#each eigene as v (v.name)}
    {#if benennt === v.name}
      <form class="speichern" onsubmit={benenne}>
        <input class="eingabe" aria-label="Neuer Name" maxlength="40" bind:value={neuerName} />
        <Knopf text="Umbenennen" symbol="check" nur klein art="submit" gesperrt={!neuerName.trim()} />
        <Knopf text="Abbrechen" symbol="xmark" nur klein frei onclick={() => (benennt = "")} />
      </form>
    {:else}
      <div class="eigene"><span class="probe" style:background={v.bg} style:color={v.fg}>{v.name}</span><Knopf text="Umbenennen" symbol="pen" nur klein frei onclick={() => ([benennt, neuerName] = [v.name, v.name])} /><Knopf text="Löschen" symbol="trash" nur klein frei onclick={() => void loesche(v)} /></div>
    {/if}
  {/each}
{/if}

<style>
  .speichern,
  .eigene {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 0.375rem;
    align-items: center;
  }
  .speichern:has(> :nth-child(2):last-child) {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .probe {
    padding: 0.25rem 0.5rem;
    border-radius: var(--r1);
    box-shadow: inset 0 0 0 1px var(--linie);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
