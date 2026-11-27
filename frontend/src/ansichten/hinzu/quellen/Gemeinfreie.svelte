<script lang="ts">
  // Gemeinfreie Bücher (BF-98): beim Tippen Vorschläge aus dem eigenen Katalog, "Bei Gutendex suchen" ausdrücklich und sichtbar
  // wartend, Störungen als Meldung; über alle Seiten auswählen und holen
  import { anzahl, zahl } from "../../../lib/format";
  import { annahme } from "../../../lib/stand/annahme.svelte";
  import { gutenberg as g, HERKUNFT } from "../../../lib/stand/gutenberg.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Gemeinfreienauftrag from "./Gemeinfreienauftrag.svelte";
  import Gemeinfreienkatalog from "./Gemeinfreienkatalog.svelte";
  import Gemeinfreientreffer from "./Gemeinfreientreffer.svelte";
  import Gutendexwarten from "./Gutendexwarten.svelte";

  const KARTE = "gemeinfreie";
  let holt = $state(false);

  $effect(() => void g.oeffneKatalog());
  // Aus einer Lücke hierher gesprungen: die Karte ins Bild, nachdem die Seite ihre Rollhöhe gesetzt hat
  $effect(() => {
    if (!g.zeigen) return;
    g.zeigen = false;
    requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById(KARTE)?.scrollIntoView({ block: "start" })));
  });

  function suche(e: SubmitEvent) {
    e.preventDefault();
    void g.suche();
  }

  async function hole() {
    holt = true;
    try {
      const n = g.zahl;
      await g.uebernimm();
      melde.gut(`${anzahl(n, "Buch wird", "Bücher werden")} geholt, Regal Gutenberg`);
    } catch (e) {
      melde.schlecht(e, "Nicht gestartet");
    } finally {
      holt = false;
    }
  }
</script>

<Karte titel="Gemeinfreie Bücher" symbol="landmark" id={KARTE}>
  <p class="leise">Aus dem Project Gutenberg. Geholte Bücher kommen ins Regal Gutenberg, schon vorhandene werden übersprungen.</p>
  <Gemeinfreienkatalog />
  <form class="suche-frei" onsubmit={suche}>
    <label class="feld">Titel oder Autor<input class="eingabe" type="search" placeholder="Faust, Fontane, Verne" bind:value={g.wort} oninput={() => g.tippe()} /></label>
    <label class="feld">Sprache<input class="eingabe" type="text" placeholder="de oder de,en" autocapitalize="none" spellcheck="false" title="Kürzel, mehrere mit Komma" bind:value={g.sprache} oninput={() => g.tippe()} /></label>
    <Knopf text="Bei Gutendex suchen" symbol="magnifying-glass" art="submit" laeuft={g.fragt} titel="Den Suchdienst fragen; er ist oft langsam" />
  </form>

  {#if g.fragt}<Gutendexwarten />{/if}
  {#if annahme.gemeinfrei.gesamt}<Gemeinfreienauftrag stand={annahme.gemeinfrei} />{/if}

  {#if g.gesucht && !g.laedt && !g.treffer.length && !g.fragt && (g.herkunft !== "katalog" || g.katalog?.da)}
    <p class="leise"><Symbol name="inbox" /> Nichts gefunden. Anderes Wort oder andere Sprache versuchen{g.herkunft === "katalog" ? ", oder bei Gutendex suchen" : ""}.</p>
  {/if}

  {#if g.treffer.length}
    <div class="reihe leiste-frei">
      <span class="zahl">{anzahl(g.gesamt, "Treffer", "Treffer")}{g.mehrereSeiten ? `, Seite ${zahl(g.seite)}` : ""}</span>
      <span class="trefferherkunft">{HERKUNFT[g.herkunft]}</span>
      <Knopf text={g.alleGewaehlt ? "Seite abwählen" : "Seite wählen"} symbol="check-double" klein onclick={() => g.schalteSeite()} />
      {#if g.zahl}<Knopf text="Auswahl aufheben" symbol="xmark" klein frei onclick={() => g.leere()} />{/if}
      <span class="schiebt"><Knopf text={g.zahl ? `${anzahl(g.zahl, "Buch", "Bücher")} holen` : "Holen"} symbol="download" klein haupt laeuft={holt} gesperrt={!g.zahl || g.laeuft} titel={g.laeuft ? "Es läuft schon eine Übernahme" : undefined} onclick={() => void hole()} /></span>
    </div>
    <div class="treffer-frei">
      {#each g.treffer as buch (buch.gutenberg_id)}<Gemeinfreientreffer {buch} gewaehlt={g.hat(buch.gutenberg_id)} onschalte={() => g.schalte(buch)} />{/each}
    </div>
    {#if g.mehrereSeiten}
      <div class="reihe">
        <Knopf text="Zurück" symbol="chevron-left" klein gesperrt={g.seite <= 1 || g.laedt || g.fragt} onclick={() => void g.blaettere(-1)} />
        <span class="zahl">Seite {zahl(g.seite)}</span>
        <Knopf text="Weiter" symbol="chevron-right" klein gesperrt={!g.weitere || g.laedt || g.fragt} onclick={() => void g.blaettere(1)} />
        {#if g.zahl}<span class="leise zahl">{zahl(g.zahl)} gewählt, die Auswahl bleibt beim Blättern</span>{/if}
      </div>
    {/if}
  {/if}
</Karte>

<style>
  .suche-frei {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: end;
  }
  .suche-frei .feld:first-child {
    flex: 1 1 14rem;
  }
  .suche-frei .feld:nth-child(2) {
    flex: 0 1 9rem;
  }
  .treffer-frei {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(auto-fill, minmax(min(19rem, 100%), 1fr));
  }
</style>
