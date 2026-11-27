<script lang="ts">
  // ISBN zur Wahl (BF-111, Abnahme 5): was der Lauf "ISBN" nicht eintragen durfte. Je Buch die beste ISBN mit Fundstelle und
  // Stufe; annehmen oder ablehnen je Zeile oder für die angehakten. Ähnliche sind vorab angehakt; abgelehnte kommen bei einem
  // neuen Lauf nicht wieder.
  import { isbnWahlAblehnen, isbnWahlAnnehmen, isbnWahlListe, type Isbnwahl } from "../../../lib/api/imports";
  import { anzahl } from "../../../lib/format";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Angabenfenster from "../../buch/Angabenfenster.svelte";
  import { Angabenwerkzeuge } from "../../buch/werkzeuge.svelte";
  import { buchziel } from "../../buch/ziel";
  import Isbnwahlzeile from "./Isbnwahlzeile.svelte";

  /** So viele zeigt die Karte zuerst */
  const ZUERST = 3;
  /** Höchstens so viele auf einmal, wie der Server liefert */
  const HOECHSTENS = 500;

  let zeilen = $state<Isbnwahl[]>([]);
  let gesamt = $state(0);
  let alle = $state(false);
  let angehakt = $state<number[]>([]);
  let arbeitet = $state<number[]>([]);
  let offen = $state<Angabenwerkzeuge | null>(null);

  $effect(() => void laden(alle));
  $effect(() => bestand.beiAenderung(() => void laden(alle)));

  async function laden(mitAllen: boolean) {
    try {
      const s = await isbnWahlListe(mitAllen ? HOECHSTENS : ZUERST);
      const bekannt = new Set(zeilen.map((z) => z.buch.id));
      zeilen = s.zeilen;
      gesamt = s.gesamt;
      angehakt = [...angehakt.filter((id) => s.zeilen.some((z) => z.buch.id === id)), ...s.zeilen.filter((z) => !bekannt.has(z.buch.id) && (z.kandidat.quelle ?? z.kandidat.text).stufe === "aehnlich").map((z) => z.buch.id)];
    } catch (e) {
      melde.schlecht(e, "ISBN zur Wahl nicht geladen");
    }
  }

  async function tue(ids: number[], annehmen: boolean) {
    if (!ids.length) return;
    arbeitet = ids;
    try {
      const { betroffen } = annehmen ? await isbnWahlAnnehmen(ids) : await isbnWahlAblehnen(ids);
      if (annehmen) melde.gut(`${anzahl(betroffen, "ISBN", "ISBN")} eingetragen`);
      else melde.info(`${anzahl(betroffen, "Buch", "Bücher")} ohne ISBN gelassen, die Vorschläge kommen nicht wieder`);
      angehakt = angehakt.filter((id) => !ids.includes(id));
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, annehmen ? "Nicht eingetragen" : "Nicht abgelehnt");
    } finally {
      arbeitet = [];
    }
  }

  function hake(id: number, an: boolean) {
    angehakt = an ? [...angehakt, id] : angehakt.filter((x) => x !== id);
  }

  async function ansehen(z: Isbnwahl) {
    const w = new Angabenwerkzeuge(z.buch, buchziel(z.buch.id, () => void laden(alle)));
    offen = w;
    await w.sucheIsbn();
    if (w.nichts) melde.info(`In ${z.buch.title} steht keine ISBN mehr`);
  }
</script>

{#if gesamt}
  <div class="zurwahl">
    <div class="reihe">
      <h3 class="isbngruppe"><Symbol name="barcode" />ISBN zur Wahl <span class="leise zahl">{gesamt}</span></h3>
      <span class="schiebt reihe"><Knopf text="Gewählte annehmen" symbol="check" klein gesperrt={!angehakt.length || !!arbeitet.length} onclick={() => void tue(angehakt, true)} /></span>
    </div>
    <div class="vorschlagsliste">
      {#each zeilen as z (z.buch.id)}
        <Isbnwahlzeile zeile={z} an={angehakt.includes(z.buch.id)} arbeitet={arbeitet.includes(z.buch.id)} onhake={(an) => hake(z.buch.id, an)} onansehen={() => void ansehen(z)}
          onannehmen={() => void tue([z.buch.id], true)} onablehnen={() => void tue([z.buch.id], false)} />
      {/each}
    </div>
    {#if !alle && gesamt > zeilen.length}<div class="reihe"><Knopf text="Alle {gesamt} zeigen" symbol="chevron-down" klein frei aufgeklappt={false} onclick={() => (alle = true)} /></div>{/if}
  </div>
{/if}

{#if offen}<Angabenfenster werkzeuge={offen} />{/if}
