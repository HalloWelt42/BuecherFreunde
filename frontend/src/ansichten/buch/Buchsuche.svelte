<script lang="ts">
  // Im Buch suchen: wörtlich mit Schaltern oder nach Bedeutung
  import { volltextSuche, type Buchtreffer } from "../../lib/api/books";
  import { sucheBedeutung } from "../../lib/api/orte";
  import { ersteMarkierung } from "../../lib/auszug";
  import { anzahl, zahl } from "../../lib/format";
  import { leseAdresse } from "../../lib/lesestand";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import type { Bedeutungstreffer, BuchEinzeln } from "../../lib/typen";
  import { stellenort, stellenziel } from "./stelle";

  let { buch }: { buch: BuchEinzeln } = $props();

  type Art = "wort" | "sinn";
  const JE_SCHRITT = 8;
  let wort = $state("");
  let art = $state<Art>("wort");
  let schalterOffen = $state(false);
  let schalter = $state({ ganzes_wort: false, gross_klein: false, regex: false });
  let woerter = $state<Buchtreffer[]>([]);
  let sinn = $state<Bedeutungstreffer[]>([]);
  let gesamt = $state(0);
  let gezeigt = $state(JE_SCHRITT);
  let sucht = $state(false);
  let stand = $state("");

  async function suche() {
    const frage = wort.trim();
    if (frage.length < 2) return;
    sucht = true;
    stand = "";
    gezeigt = JE_SCHRITT;
    try {
      if (art === "wort") {
        const a = await volltextSuche(buch.id, frage, schalter);
        woerter = a.treffer;
        gesamt = a.gesamt;
        stand = gesamt ? anzahl(gesamt, "Stelle", "Stellen") : "Keine Stelle gefunden.";
      } else {
        const a = await sucheBedeutung(frage, 20, buch.id);
        sinn = a.treffer;
        stand = !a.verfuegbar ? (a.grund ?? "Die Suche nach Bedeutung ist gerade nicht da.") : a.treffer.length ? anzahl(a.treffer.length, "Stelle", "Stellen") : "Keine Stelle gefunden.";
      }
    } catch (e) {
      stand = e instanceof Error ? e.message : String(e);
      woerter = [];
      sinn = [];
    } finally {
      sucht = false;
    }
  }

  function setzeArt(neu: Art) {
    art = neu;
    stand = "";
    void suche();
  }

  function setzeSchalter(name: keyof typeof schalter, an: boolean) {
    schalter[name] = an;
    void suche();
  }

  // Der Sprung zeigt die Stelle (stelle.ts)
  const ziel = (t: Buchtreffer) => stellenziel(buch, t, ersteMarkierung(t.kontext) || wort.trim());
  const ort = (t: Buchtreffer) => stellenort(buch, t);
  let laenge = $derived(art === "wort" ? woerter.length : sinn.length);
</script>

<Karte titel="Im Buch suchen" symbol="magnifying-glass">
  <form class="reihe" onsubmit={(e) => { e.preventDefault(); void suche(); }}>
    <input class="eingabe feldwort" type="search" bind:value={wort} aria-label="Suchwort" placeholder={art === "wort" ? "Wort oder Satz" : "Worum es gehen soll"} enterkeyhint="search" />
    {#if anschluesse.jetzt.bedeutung}<Segment name="Suche im Buch" werte={[["wort", "Wörtlich"], ["sinn", "Bedeutung"]]} wert={art} onwahl={setzeArt} />{/if}
    <Knopf text="Suchen" symbol="magnifying-glass" nur klein art="submit" laeuft={sucht} gesperrt={wort.trim().length < 2} />
  </form>
  {#if stand}<p class="leise zahl" role="status">{stand}</p>{/if}

  <div>
    {#if art === "wort"}
      {#each woerter.slice(0, gezeigt) as t, n (n)}
        <div class="stelle"><i></i><span class="zitat"><Auszug text={t.kontext} /></span><Chip text={ort(t)} href={ziel(t)} /></div>
      {/each}
    {:else}
      {#each sinn.slice(0, gezeigt) as t, n (n)}
        <div class="stelle"><i></i><span><span class="zitat">{t.auszug}</span><br /><span class="leise">{t.naehe}{t.gedruckt ? `, gedruckt ${t.gedruckt}` : ""}</span></span><Chip text={t.seite ? `Seite ${zahl(t.seite)}` : "Öffnen"} href={leseAdresse(buch.id, { page: t.seite ?? undefined, stelle: t.auszug.slice(0, 80) })} /></div>
      {/each}
    {/if}
  </div>
  <div class="reihe">
    {#if laenge > gezeigt}<Knopf text="Weitere {Math.min(JE_SCHRITT, laenge - gezeigt)} zeigen" symbol="chevron-down" klein onclick={() => (gezeigt += JE_SCHRITT)} />{/if}
    {#if art === "wort"}<Knopf text="Ganzes Wort, Groß und klein, Muster" symbol="sliders" klein frei aufgeklappt={schalterOffen} onclick={() => (schalterOffen = !schalterOffen)} />{/if}
  </div>
  {#if schalterOffen && art === "wort"}
    <div class="reihe">
      <Haekchen text="Ganzes Wort" an={schalter.ganzes_wort} onwahl={(an) => setzeSchalter("ganzes_wort", an)} />
      <Haekchen text="Groß und klein unterscheiden" an={schalter.gross_klein} onwahl={(an) => setzeSchalter("gross_klein", an)} />
      <Haekchen text="Muster (regulärer Ausdruck)" an={schalter.regex} onwahl={(an) => setzeSchalter("regex", an)} />
    </div>
  {/if}
</Karte>

<style>
  .feldwort {
    flex: 1 1 8rem;
  }
</style>
