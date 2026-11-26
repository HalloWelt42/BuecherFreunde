<script lang="ts">
  // Vorlesen im Leser: was gelesen wird (Seite, Kapitel, ab hier, ganzes Buch, weiter an der gemerkten Stelle), der Spieler,
  // Stimme, Tempo, Schlafuhr
  import { coverUrl } from "../../lib/api/books";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { TEMPI, vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Schlaf } from "../../lib/vorlesen/folge";
  import type { Strecke } from "../../lib/vorlesen/typen";
  import Spieler from "./Spieler.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  type Umfang = "seite" | "kapitel" | "hier" | "buch";
  const UMFAENGE: [Umfang, string, string][] = [["seite", "Diese Seite", "file-lines"], ["kapitel", "Dieses Kapitel", "bookmark"], ["hier", "Ab hier", "play"], ["buch", "Ganzes Buch", "book-open"]];

  let laedt = $state<Umfang | "weiter" | "">("");
  let quelle = $derived(sitzung.quelle);
  let hier = $derived(vorlesen.aktiv && !!quelle && vorlesen.quelle === quelle);
  let art = $derived(quelle?.einheitsart ?? "Seite");
  let tempo = $derived(TEMPI.indexOf(vorlesen.tempo));

  const SCHLAF: [string, Schlaf][] = [["aus", { art: "aus" }], ["einheit", { art: "einheit" }], ["kapitel", { art: "kapitel" }], ["15", { art: "minuten", minuten: 15 }], ["30", { art: "minuten", minuten: 30 }], ["60", { art: "minuten", minuten: 60 }]];
  let schlafwerte = $derived<[string, string][]>(SCHLAF.filter(([w]) => w !== "kapitel" || quelle?.mitKapiteln).map(([w, s]) => [w, s.art === "aus" ? "Aus" : s.art === "einheit" ? `Ende ${art === "Seite" ? "der Seite" : art === "Abschnitt" ? "des Abschnitts" : "des Stücks"}` : s.art === "kapitel" ? "Ende des Kapitels" : `Nach ${s.minuten} Minuten`]));
  let schlafwert = $derived(vorlesen.schlaf.art === "minuten" ? String(vorlesen.schlaf.minuten) : vorlesen.schlaf.art);

  $effect(() => vorlesen.pruefe());
  // Wo das Vorlesen zuletzt stehen blieb, auch auf einem anderen Gerät (BF-37)
  $effect(() => void vorlesen.ladeStelle(sitzung.buch.id));
  let gemerkt = $derived(vorlesen.gemerkt?.buch === sitzung.buch.id ? vorlesen.gemerkt.stelle : null);

  async function strecke(u: Umfang): Promise<Strecke | null> {
    if (!quelle) return null;
    if (u === "buch") return { von: { einheit: 0, zeichen: 0 }, bis: null };
    if (u === "hier") return { von: await quelle.hier(), bis: null };
    return u === "seite" ? quelle.seite() : quelle.kapitel();
  }

  async function starte(u: Umfang | "weiter", name: string) {
    // Im Tippen selbst, sonst bleibt das Telefon stumm
    vorlesen.entsperre();
    laedt = u;
    try {
      const s = u === "weiter" ? weiterAb() : await strecke(u);
      if (!s || !quelle) return void melde.info("Hier gibt es nichts zum Vorlesen");
      const b = sitzung.buch;
      vorlesen.liesBuch(quelle, s, name, { titel: b.title, autor: b.authors.map((a) => a.name).join(", "), bild: coverUrl(b.id) }, b.id);
    } finally {
      laedt = "";
    }
  }

  /** Weiter am gemerkten Satz, bis zum Ende des Umfangs, der damals gewählt war */
  function weiterAb(): Strecke | null {
    if (!gemerkt) return null;
    const bis = gemerkt.bis_einheit === null ? null : { einheit: gemerkt.bis_einheit, zeichen: gemerkt.bis_zeichen ?? 0 };
    return { von: { einheit: gemerkt.einheit, zeichen: gemerkt.zeichen }, bis };
  }
</script>

<div class="vorlesen">
  {#if hier}
    <div class="stand">
      <Symbol name={vorlesen.wartet && !vorlesen.pausiert ? "circle-notch" : vorlesen.pausiert ? "pause" : "volume-high"} dreht={vorlesen.wartet && !vorlesen.pausiert} />
      <span><b>{vorlesen.name}</b><span class="leise"> · {vorlesen.wartet && !vorlesen.pausiert ? "Ton wird geholt" : vorlesen.pausiert ? "Angehalten" : vorlesen.was}</span></span>
    </div>
    <Spieler {art} />
    {#if vorlesen.weg}<Knopf text="Zur Stelle" symbol="location-crosshairs" klein onclick={() => vorlesen.zurStelle()} />{/if}
  {:else}
    <div class="tastenraster" style:--spalten="2" role="group" aria-label="Vorlesen">
      {#if gemerkt}
        <Knopf klasse="kachel weiter" text="Weiterlesen" symbol="forward" laeuft={laedt === "weiter"} gesperrt={!quelle || !vorlesen.stimmen.length} titel="Weiter an der Stelle, an der es stehen blieb" onclick={() => void starte("weiter", gemerkt?.umfang || "Weiterlesen")}><span class="ab">ab {gemerkt.ort}</span></Knopf>
      {/if}
      {#each UMFAENGE as [u, name, symbol] (u)}
        {#if u !== "kapitel" || quelle?.mitKapiteln}
          <Knopf klasse="kachel" text={name} {symbol} laeuft={laedt === u} gesperrt={!quelle || !vorlesen.stimmen.length} titel={u === "buch" ? "Ganzes Buch von vorn" : undefined} onclick={() => void starte(u, name)} />
        {/if}
      {/each}
    </div>
  {/if}
  {#if vorlesen.stimmen.length}
    <div class="regelzeile">
      <span class="klein">Stimme</span>
      <Auswahl name="Stimme" gruppen={vorlesen.gruppen} wert={vorlesen.stimme} onwahl={(id) => vorlesen.waehle(id)} />
      <Knopf text="Probe hören" symbol="play" nur klein gesperrt={vorlesen.aktiv} onclick={() => { vorlesen.entsperre(); vorlesen.probe(); }} />
    </div>
    <div class="regelzeile">
      <span class="klein">Tempo</span>
      <span class="klein zahl tempo">{vorlesen.tempo.toLocaleString("de-DE")} ×</span>
      <span class="reihe">
        <Knopf text="Langsamer" symbol="minus" nur klein gesperrt={tempo <= 0} onclick={() => (vorlesen.tempo = TEMPI[tempo - 1])} />
        <Knopf text="Schneller" symbol="plus" nur klein gesperrt={tempo >= TEMPI.length - 1} onclick={() => (vorlesen.tempo = TEMPI[tempo + 1])} />
      </span>
    </div>
    {#if hier}
      <div class="regelzeile">
        <span class="klein">Schlafuhr</span>
        <Auswahl name="Schlafuhr" werte={schlafwerte} wert={schlafwert} onwahl={(w) => vorlesen.setzeSchlaf(SCHLAF.find(([x]) => x === w)![1])} />
      </div>
    {/if}
  {:else}
    <p class="klein leise">{vorlesen.hinweis || "Hier gibt es keine Stimme zum Vorlesen."}</p>
  {/if}
  {#if vorlesen.hinweis && vorlesen.stimmen.length}<p class="klein leise">{vorlesen.hinweis}</p>{/if}
</div>

<style>
  .vorlesen {
    display: grid;
    gap: 0.5rem;
    min-width: 0;
  }
  .stand {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.5rem;
    align-items: center;
    font-size: 0.875rem;
  }
  .stand b {
    font-weight: 600;
  }
  .regelzeile {
    display: grid;
    grid-template-columns: 4.5rem minmax(0, 1fr) auto;
    gap: 0.5rem;
    align-items: center;
  }
  .tempo {
    text-align: center;
  }
  /* Weiterlesen steht über den Umfängen, so breit wie zwei */
  .vorlesen :global(.kachel.weiter) {
    grid-column: 1 / -1;
  }
  .ab {
    font-size: 0.8125rem;
    color: var(--tinte-3);
  }
  .reihe {
    gap: 0.25rem;
    flex-wrap: nowrap;
  }
</style>
