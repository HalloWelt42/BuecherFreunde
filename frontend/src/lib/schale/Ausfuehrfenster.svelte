<script lang="ts">
  // Ausführen (BF-29, Entwurf ausfuehren.html): Listings aus dem Buch in der Sandbox der Codeschmiede laufen lassen und
  // Schritt für Schritt ansehen. Das Fenster liegt in der Schale wie Nachschlagen, nicht im Leser: Blättern, Suchsprünge,
  // Wechsel zwischen Original und Text und Vollbild lassen es stehen. Erst beim ersten Öffnen geladen, mit Editor und
  // Debugger des Appkerns. Je Tab bleiben Editor und Sitzung eingehängt, nur verborgen; als Leiste abgelegt ebenso.
  // Am Telefon ein Blatt unten ohne Editor.
  import "../../stil/ausfuehren.css";
  import { EditorBereich, type Funktionsbestand } from "appkern-oberflaeche/code";
  import { onDestroy } from "svelte";
  import { ausfuehrstand, ENDUNGEN, phpFunktionen, SPRACHNAMEN, SPRACHSYMBOLE, type Ausfuehrstand, type Codesprache } from "../api/ausfuehren";
  import { Arbeit } from "../ausfuehren/arbeit.svelte";
  import { bestandFuer, passendeFassung } from "../ausfuehren/fassungen";
  import Debugansicht from "../ausfuehren/Debugansicht.svelte";
  import Telefonblatt from "../ausfuehren/Telefonblatt.svelte";
  import { ausfuehren } from "../stand/ausfuehren.svelte";
  import { darstellung } from "../stand/darstellung.svelte";
  import { frage } from "../stand/rueckfrage.svelte";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Schwebefenster from "../teile/Schwebefenster.svelte";
  import Symbol from "../teile/Symbol.svelte";

  const KUERZEL = /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘↵" : "Strg ↵";

  // Je Tab eine Arbeit (Kopie, Sitzung, Schritt); sie bleibt, solange der Tab offen ist
  const vorrat = new Map<string, Arbeit>();
  function arbeitFuer(k: string): Arbeit {
    let a = vorrat.get(k);
    if (!a) {
      a = new Arbeit(k);
      vorrat.set(k, a);
    }
    return a;
  }
  let arbeiten = $derived(ausfuehren.tabs.filter((k) => ausfuehren.kopie(k)).map(arbeitFuer));
  let aktiv = $derived(arbeiten.find((a) => a.k === ausfuehren.aktiv) ?? arbeiten[0] ?? null);
  let kopie = $derived(aktiv?.kopie ?? null);

  let stand = $state.raw<Ausfuehrstand | null>(null);
  let alleFunktionen = $state.raw<Record<string, string[]>>({});
  $effect(() => void ausfuehrstand().then((s) => (stand = s)));
  $effect(() => {
    if (arbeiten.some((a) => a.sprache === "php")) void phpFunktionen().then((b) => (alleFunktionen = b));
  });

  const angebotFuer = (sprache: Codesprache) => (stand?.bereit ? (stand.sprachen.find((s) => s.sprache === sprache) ?? null) : null);
  let angebot = $derived(kopie ? angebotFuer(kopie.sprache) : null);
  let fassungen = $derived(angebot?.fassungen ?? []);
  let fassung = $derived(kopie ? passendeFassung(fassungen, kopie.fassung) : "");
  let kann = $derived(!!angebot);
  let aufzeichnen = $derived(!!angebot?.aufzeichnen);
  const bestand = (a: Arbeit): Funktionsbestand | null => {
    const f = passendeFassung(angebotFuer(a.sprache)?.fassungen ?? [], a.kopie?.fassung ?? "");
    return a.sprache === "php" && f ? bestandFuer(SPRACHNAMEN.php, f, alleFunktionen) : null;
  };
  let lage = $derived<{ text: string; led: string; titel: string }>(
    !stand ? { text: "Frage die Sandbox ...", led: "", titel: "" }
      : kann ? { text: "Sandbox bereit", led: "gut", titel: "Sandbox der Codeschmiede: ohne Netz, nur lesend, mit Grenzen für Zeit und Speicher" }
      : stand.bereit && kopie ? { text: `${SPRACHNAMEN[kopie.sprache]} läuft hier nicht`, led: "warn", titel: "" }
      : { text: stand.grund || "Sandbox nicht erreichbar", led: "schlecht", titel: stand.grund },
  );

  /** Sprachen und Fassungen zur Wahl, als Werte "sprache:fassung" */
  let wahlen = $derived(
    (stand?.sprachen ?? []).flatMap((s) => (s.fassungen.length ? s.fassungen.map((f) => [`${s.sprache}:${f}`, `${SPRACHNAMEN[s.sprache]} ${f}`]) : [[`${s.sprache}:`, SPRACHNAMEN[s.sprache]]])),
  );
  function waehle(wert: string) {
    if (!aktiv) return;
    const [sprache, f] = wert.split(":") as [Codesprache, string];
    ausfuehren.aendere(aktiv.k, { sprache, fassung: f });
    aktiv.sitzung.beenden();
  }

  const dateiname = (a: Arbeit) => {
    const d = a.kopie?.listing.datei.split("/").at(-1);
    return d || `listing.${ENDUNGEN[a.sprache]}`;
  };
  let untertitel = $derived(kopie ? [kopie.listing.buchtitel, [kopie.listing.titel, kopie.listing.seiten ? `S. ${kopie.listing.seiten}` : ""].filter(Boolean).join(", ")].filter(Boolean).join(" · ") : "");

  function starte(reiter: "ausgabe" | "debugger") {
    if (aktiv && kann && (reiter === "ausgabe" || aufzeichnen)) aktiv.starte(reiter, fassung);
  }

  async function zuruecksetzen() {
    if (!aktiv || !kopie) return;
    const ja = await frage({ titel: "Kopie zurücksetzen?", folgen: [`Deine Änderungen an ${dateiname(aktiv)} gehen verloren; es gilt wieder das Listing aus dem Buch.`], ja: "Zurücksetzen" });
    if (!ja) return;
    ausfuehren.zuruecksetzen(aktiv.k);
    aktiv.sitzung.beenden();
  }

  function schliesseTab(a: Arbeit) {
    a.zerstoere();
    vorrat.delete(a.k);
    ausfuehren.schliesseTab(a.k);
  }

  /** Ausführen mit Cmd oder Strg und Enter, vor dem Editor abgefangen, der damit sonst eine Zeile einfügt */
  function tasteVorab(e: KeyboardEvent) {
    if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    e.stopPropagation();
    starte("ausgabe");
  }

  let ed = $derived(darstellung.dunkel ? "dunkel" : "hell");
  let schritt = $derived(aktiv && aktiv.schritte.length ? `Schritt ${aktiv.i + 1} von ${aktiv.schritte.length}` : "");

  onDestroy(() => {
    for (const a of vorrat.values()) a.zerstoere();
  });
</script>

{#if schale.telefon}
  {#if aktiv}
    <Telefonblatt arbeit={aktiv} name={dateiname(aktiv)} {kann} {fassung} {ed} onzurstelle={() => ausfuehren.zurStelle(aktiv.k)} onschliessen={() => ausfuehren.schliesse()} onzuruecksetzen={() => void zuruecksetzen()} />
  {/if}
{:else}
  {#if ausfuehren.abgelegt && aktiv}
    <div class="ausfuehrleiste glas dicht" role="region" aria-label="Ausführen, abgelegt" data-ed={ed}>
      <Symbol name="play" /><b>{dateiname(aktiv)}</b>{#if schritt}<span class="leise zahl">{schritt}</span>{/if}
      <Knopf text="Wieder öffnen" symbol="up-right-and-down-left-from-center" nur klein frei onclick={() => ausfuehren.aufnehmen()} />
    </div>
  {/if}
  <!-- Abgelegt bleibt alles eingehängt, nur verborgen: Rückgängig, Haltepunkte und Schritt bleiben -->
  <Schwebefenster merkname="bf-ausfuehren-ort" titel="Ausführen" {untertitel} symbol="play" klasse="ausfuehrfenster{ausfuehren.abgelegt ? ' abgelegt' : ''}" stufe={1} onschliessen={() => ausfuehren.schliesse()} data-ed={ed} data-eigene-tasten="">
      {#snippet knoepfe()}
        <Knopf text="Zur Stelle im Buch" symbol="location-crosshairs" nur klein frei gesperrt={!aktiv} onclick={() => aktiv && ausfuehren.zurStelle(aktiv.k)} />
        <Knopf text="Als Leiste ablegen" symbol="window-minimize" nur klein frei onclick={() => ausfuehren.ablegen()} />
      {/snippet}

      <!-- Unter dem Kopf: wird es eng, wird erst der Editor kleiner, dann rollt alles (stil/ausfuehren.css) -->
      <div class="koerper">
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="werkzeug" onkeydowncapture={tasteVorab}>
          <Knopf text="Ausführen" symbol="play" klein haupt laeuft={!!aktiv?.sitzung.laeuft && aktiv.reiter === "ausgabe"} gesperrt={!kann || !!aktiv?.sitzung.laeuft} titel="In der Sandbox ausführen ({KUERZEL})" onclick={() => starte("ausgabe")}><kbd>{KUERZEL}</kbd></Knopf>
          {#if aufzeichnen}<Knopf text="Debuggen" symbol="bug" klein gedrueckt={aktiv?.reiter === "debugger" && !!aktiv.sitzung.lauf} gesperrt={!kann || !!aktiv?.sitzung.laeuft} titel="Lauf aufzeichnen und Schritt für Schritt ansehen" onclick={() => starte("debugger")} />{/if}
          <Knopf text="Zurücksetzen" symbol="rotate-left" klein frei gesperrt={!aktiv?.geaendert} titel="Wieder das Listing aus dem Buch" onclick={() => void zuruecksetzen()} />
          {#if kopie}
            <label class="chip sprachwahl" title="Sprache und Fassung, in der der Code läuft">
              <Symbol name={SPRACHSYMBOLE[kopie.sprache]} art="brands" />
              {#if wahlen.length}
                <select aria-label="Sprache und Fassung" value="{kopie.sprache}:{fassung}" onchange={(e) => waehle(e.currentTarget.value)}>
                  {#each wahlen as [w, t] (w)}<option value={w}>{t}</option>{/each}
                </select>
              {:else}{SPRACHNAMEN[kopie.sprache]}{/if}
            </label>
          {/if}
          <span class="lage" title={lage.titel}><span class="led {lage.led}"></span>{lage.text}</span>
        </div>

        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="flaeche" onkeydowncapture={tasteVorab}>
          <div class="dateien" role="tablist" aria-label="Offene Listings">
            {#each arbeiten as a (a.k)}
              <span class="datei" class:an={a === aktiv}>
                <button type="button" role="tab" aria-selected={a === aktiv} title={[a.kopie?.listing.datei || dateiname(a), a.kopie?.listing.buchtitel, a.kopie?.listing.titel].filter(Boolean).join(" · ")} onclick={() => ausfuehren.waehle(a.k)}>
                  <Symbol name={SPRACHSYMBOLE[a.sprache]} art="brands" />{dateiname(a)}{#if a.geaendert}<span class="geaendert" title="Geändert"></span>{/if}
                </button>
                {#if a !== aktiv}<button type="button" class="x" aria-label="{dateiname(a)} schließen" title="Tab schließen" onclick={() => schliesseTab(a)}><Symbol name="xmark" /></button>{/if}
              </span>
            {/each}
            <span class="rest" title="Du arbeitest an einer Kopie; das Buch bleibt, wie es ist"><Symbol name="circle-info" />Kopie</span>
          </div>
          {#each arbeiten as a (a.k)}
            <div class="editorplatz" hidden={a !== aktiv}>
              {#if stand}
                {#key a.sprache}
                  <EditorBereich sprache={a.sprache} bind:code={a.code} markierteZeile={a.markiert} mitHaltepunkten={!!angebotFuer(a.sprache)?.aufzeichnen} bind:haltepunkte={a.haltepunkte} bestand={bestand(a)} werte={a.rahmen} />
                {/key}
              {/if}
            </div>
          {/each}
        </div>

        {#if aktiv}<Debugansicht arbeit={aktiv} {aufzeichnen} />{/if}
        <div class="fuss"><Symbol name="circle-info" />{aufzeichnen ? "Klick links neben die Zeilennummer setzt einen Haltepunkt" : "Du arbeitest an einer Kopie; das Buch bleibt, wie es ist"}</div>
      </div>
  </Schwebefenster>
{/if}
