<script lang="ts">
  // Kategorien aus Importen (BF-69): alte Regale gehen im Katalog auf. Je Ziel eine Zeile: die alten Namen, der Pfeil, die
  // Kategorie oder "Schlagwort am Buch". Übernehmen setzt die Bücher dorthin; entfernt wird ein altes Regal erst nach der
  // Folgenvorschau, nie von selbst.
  import { SvelteMap } from "svelte/reactivity";
  import { altfolgen, entferneAltes, ladeAlte, uebernimmAlte } from "../../../lib/api/katalog";
  import { anzahl } from "../../../lib/format";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { frage } from "../../../lib/stand/rueckfrage.svelte";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Kategoriewahl from "../../../lib/teile/Kategoriewahl.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Menue from "../../../lib/teile/Menue.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { AltesRegal, Altziel } from "../../../lib/typen";
  import { altzeilen, type Altzeile } from "./alte";

  /** So viele Namen nennt die Rückfrage, der Rest steht als Zahl */
  const NAMEN_HOECHSTENS = 8;

  let alte = $state<AltesRegal[]>([]);
  let geladen = $state(false);
  /** Eigene Wahl des Ziels je altem Regal */
  const gewaehlt = new SvelteMap<number, Altziel>();
  /** Übernommene Zeilen dieser Sitzung */
  let uebernommen = $state<ReadonlySet<string>>(new Set());
  let arbeitet = $state("");
  /** Ziel wählen für diese alten Regale, am Knopf oder am Namen */
  let wahl = $state<{ ids: number[]; anker: HTMLElement } | null>(null);

  let zeilen = $derived(altzeilen(alte, bestand.katalog, gewaehlt));

  $effect(() => void laden());

  async function laden() {
    try {
      alte = await ladeAlte();
    } catch {
      alte = [];
    } finally {
      geladen = true;
    }
  }

  async function uebernimm(z: Altzeile) {
    if (!z.ziel) return;
    arbeitet = z.schluessel;
    try {
      const { buecher } = await uebernimmAlte(z.alte.map((a) => a.id), z.ziel);
      uebernommen = new Set([...uebernommen, z.schluessel]);
      melde.gut(`${anzahl(buecher, "Buch", "Bücher")} übernommen nach ${z.name}`);
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht übernommen");
    } finally {
      arbeitet = "";
    }
  }

  async function entferne(ids: number[]) {
    const betroffen = alte.filter((a) => ids.includes(a.id));
    let folgen;
    try {
      folgen = await Promise.all(betroffen.map((a) => altfolgen(a.id)));
    } catch (e) {
      melde.schlecht(e);
      return;
    }
    const buecher = folgen.reduce((s, f) => s + f.buecher, 0);
    const ohne = folgen.reduce((s, f) => s + f.ohne_kategorie, 0);
    const namen = folgen.slice(0, NAMEN_HOECHSTENS).map((f) => `${f.name}: ${anzahl(f.buecher, "Buch", "Bücher")}${f.titel.length ? `, etwa ${f.titel.slice(0, 3).join(", ")}` : ""}`);
    const ja = await frage({
      titel: betroffen.length === 1 ? `Altes Regal ${betroffen[0].name} entfernen?` : `${anzahl(betroffen.length, "altes Regal", "alte Regale")} entfernen?`,
      folgen: [
        ...namen,
        ...(betroffen.length > NAMEN_HOECHSTENS ? [`und ${anzahl(betroffen.length - NAMEN_HOECHSTENS, "weiteres", "weitere")}`] : []),
        buecher ? `${anzahl(buecher, "Buch verliert", "Bücher verlieren")} diese Regale, die Bücher selbst bleiben.` : "Kein Buch steht darin.",
        ...(ohne ? [`${anzahl(ohne, "Buch steht", "Bücher stehen")} noch in keiner Kategorie des Katalogs.`] : []),
      ],
      ja: "Entfernen",
    });
    if (!ja) return;
    const fort: number[] = [];
    for (const a of betroffen) {
      try {
        await entferneAltes(a.id);
        fort.push(a.id);
      } catch (e) {
        melde.schlecht(e, `${a.name} nicht entfernt`);
      }
    }
    alte = alte.filter((a) => !fort.includes(a.id));
    if (fort.length) {
      melde.gut(`${anzahl(fort.length, "altes Regal", "alte Regale")} entfernt`);
      bestand.geaendert();
    }
  }

  function setzeZiel(ziel: Altziel) {
    for (const id of wahl?.ids ?? []) gewaehlt.set(id, ziel);
    wahl = null;
  }

  const oeffneWahl = (ids: number[], e: MouseEvent) => (wahl = { ids, anker: e.currentTarget as HTMLElement });
</script>

{#if geladen && alte.length}
  <Karte titel="Kategorien aus Importen" symbol="tags" breit id="katalog-alt">
    <div class="altliste">
      {#each zeilen as z (z.schluessel)}
        <div class="altzeile platte">
          <span class="alt">{#each z.alte as a (a.id)}<Chip text={a.name} titel="{anzahl(a.anzahl, 'Buch', 'Bücher')}, Ziel wählen" onclick={(e) => oeffneWahl([a.id], e)} />{/each}</span>
          <Symbol name="arrow-right" klasse="leise pfeil" />
          <span class="neu"><Katalogzeichen name={z.zeichen} farbe={z.farbe} /><span>{z.name}<small>{z.unter}</small></span></span>
          <span class="reihe griffe">
            <Knopf text={uebernommen.has(z.schluessel) ? "Übernommen" : "Übernehmen"} symbol={uebernommen.has(z.schluessel) ? "check-double" : "check"} nur klein frei laeuft={arbeitet === z.schluessel} gesperrt={!z.ziel} onclick={() => void uebernimm(z)} />
            <Knopf text="Ziel wählen" symbol="pen" nur klein frei onclick={(e) => oeffneWahl(z.alte.map((a) => a.id), e)} />
            <Knopf text="Alte Regale entfernen" symbol="trash" nur klein frei onclick={() => void entferne(z.alte.map((a) => a.id))} />
          </span>
        </div>
      {/each}
    </div>
  </Karte>
{/if}

{#if wahl && bestand.katalog}
  <Menue anker={wahl.anker} name="Ziel wählen" onschliessen={() => (wahl = null)}>
    <button type="button" class="punkt" onclick={() => setzeZiel({ schlagwort: true })}><Symbol name="tag" /><span class="name">Schlagwort am Buch</span></button>
    {#if wahl.ids.length === 1}
      <button type="button" class="punkt" onclick={() => { const ids = wahl?.ids ?? []; wahl = null; void entferne(ids); }}><Symbol name="trash" /><span class="name">Entfernen</span></button>
    {/if}
    <Kategoriewahl bereiche={bestand.katalog.bereiche} onwahl={(k) => k.id !== undefined && setzeZiel({ kategorie_id: k.id })} />
  </Menue>
{/if}
