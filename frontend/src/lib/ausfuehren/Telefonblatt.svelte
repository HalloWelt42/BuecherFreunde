<script lang="ts">
  // Ausführen am Telefon (BF-29): ein Blatt unten über der Tafel. Ausführen zeichnet jeden Lauf auf; fünf gleich hohe
  // Tasten ohne Beschriftung; Reiter Code: fünf Zeilen um die gezeigte, darunter die Werte; Reiter Bearbeiten (BF-105): der
  // ganze Code im Editor, Zurücksetzen holt das Listing aus dem Buch, mit offener Tastatur wächst das Blatt nach oben; Reiter
  // Ausgabe. Ein Tipp auf die Nummer einer Zeile setzt oder löscht den Haltepunkt.
  import { EditorBereich, type Ziel } from "appkern-oberflaeche/code";
  import { onDestroy } from "svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import type { Arbeit } from "./arbeit.svelte";
  import { faerbeZeilen } from "./zeilen";

  let { arbeit, name, kann, fassung, ed, onzurstelle, onschliessen, onzuruecksetzen }: { arbeit: Arbeit; name: string; kann: boolean; fassung: string; ed: string; onzurstelle: () => void; onschliessen: () => void; onzuruecksetzen: () => void } = $props();

  const UMKREIS = 2;
  const GRIFFE: { ziel: Ziel; symbol: string; titel: string }[] = [
    { ziel: "zurueckHalt", symbol: "backward", titel: "Zurück zum vorigen Haltepunkt" },
    { ziel: "zurueck", symbol: "backward-step", titel: "Schritt zurück" },
    { ziel: "hinein", symbol: "forward-step", titel: "Schritt vor" },
    { ziel: "weiterHalt", symbol: "forward", titel: "Weiter bis zum nächsten Haltepunkt" },
  ];

  let wahl = $state<"code" | "bearbeiten" | "ausgabe">("code");

  // Beim Bearbeiten wächst das Blatt mit offener Tastatur nach oben: unten bleibt so viel frei, wie die Tastatur verdeckt
  let tastatur = $state(0);
  const vv = typeof window !== "undefined" ? window.visualViewport : null;
  const miss = () => (tastatur = vv ? Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop)) : 0);
  vv?.addEventListener("resize", miss);
  vv?.addEventListener("scroll", miss);
  onDestroy(() => {
    vv?.removeEventListener("resize", miss);
    vv?.removeEventListener("scroll", miss);
  });
  let zeilen = $state<string[]>([]);
  $effect(() => {
    const [code, sprache] = [arbeit.code, arbeit.sprache];
    void faerbeZeilen(code, sprache).then((z) => (zeilen = z));
  });

  let n = $derived(arbeit.schritte.length);
  let jetzt = $derived(arbeit.veraltet ? null : (arbeit.aktuell?.zeile ?? null));
  // Mit Lauf fünf Zeilen um die gezeigte, ohne Lauf alle zum Setzen der Haltepunkte
  let sichtbar = $derived.by(() => {
    const alle = zeilen.map((html, k) => ({ nr: k + 1, html }));
    if (jetzt === null) return alle;
    const von = Math.max(1, Math.min(jetzt - UMKREIS, alle.length - 2 * UMKREIS));
    return alle.slice(von - 1, von - 1 + 2 * UMKREIS + 1);
  });

  function schalte(nr: number) {
    const h = arbeit.haltepunkte;
    arbeit.haltepunkte = h.includes(nr) ? h.filter((z) => z !== nr) : [...h, nr].sort((a, b) => a - b);
  }
  function ausfuehren() {
    wahl = "code";
    arbeit.starte("debugger", fassung);
  }
</script>

<section class="schwebefenster glas dicht blatt-sheet" class:hoch={wahl === "bearbeiten"} style:--tastatur="{tastatur}px" aria-label="Ausführen" data-ed={ed} data-eigene-tasten>
  <div class="zug"></div>
  <header>
    <div class="titel"><b>{name}</b><span class="zahl">{arbeit.geaendert ? "geändert, " : ""}{n ? `Schritt ${arbeit.i + 1} von ${n}${jetzt ? ` · Zeile ${jetzt}` : ""}` : arbeit.sitzung.laeuft ? "Zeichne den Lauf auf ..." : "Noch kein Lauf"}</span></div>
    <Knopf text="Zur Stelle" symbol="location-crosshairs" nur frei onclick={onzurstelle} />
    <Knopf text="Schließen" symbol="xmark" nur frei onclick={onschliessen} />
  </header>
  <div class="griffe">
    <Knopf text="Ausführen" symbol="play" nur haupt laeuft={arbeit.sitzung.laeuft} gesperrt={!kann} onclick={ausfuehren} />
    {#each GRIFFE as g (g.ziel)}<Knopf text={g.titel} symbol={g.symbol} nur gesperrt={!n || arbeit.ziel(g.ziel) === arbeit.i} onclick={() => arbeit.gehe(g.ziel)} />{/each}
  </div>
  <div class="wahl">
    <div class="segment" role="group" aria-label="Code oder Ausgabe">
      <button type="button" aria-pressed={wahl === "code"} onclick={() => (wahl = "code")}><Symbol name="code" />Code</button>
      <button type="button" aria-pressed={wahl === "bearbeiten"} onclick={() => (wahl = "bearbeiten")}><Symbol name="pen" />Bearbeiten</button>
      <button type="button" aria-pressed={wahl === "ausgabe"} onclick={() => (wahl = "ausgabe")}><Symbol name="terminal" />Ausgabe</button>
    </div>
  </div>
  {#if wahl === "code"}
    <div class="inhalt">
      <pre class="zeilen">{#each sichtbar as z (z.nr)}<span class="z" class:halt={arbeit.haltepunkte.includes(z.nr)} class:jetzt={z.nr === jetzt}><button type="button" class="nr" aria-label="Haltepunkt in Zeile {z.nr}" aria-pressed={arbeit.haltepunkte.includes(z.nr)} onclick={() => schalte(z.nr)}>{z.nr}</button><span>{@html z.html || " "}</span></span>{/each}</pre>
      {#if arbeit.variablen.length}
        <div class="feldchen"><dl class="werte">{#each arbeit.variablen as v (v.name)}<dt>{v.name}</dt><dd class:neu={v.neu} title={v.wert}>{v.wert}</dd>{/each}</dl></div>
      {/if}
      {#if arbeit.sitzung.fehler}<div class="meldung-lauf"><Symbol name="triangle-exclamation" /><span>{arbeit.sitzung.fehler}</span></div>{/if}
    </div>
  {:else if wahl === "bearbeiten"}
    <div class="inhalt bearbeiten">
      <div class="editorplatz">
        {#key arbeit.sprache}<EditorBereich sprache={arbeit.sprache} bind:code={arbeit.code} />{/key}
      </div>
      <div class="bearbeitet">
        {#if arbeit.geaendert}<span class="geaendert"><Symbol name="pen" />geändert</span><span>das Listing im Buch bleibt</span>{:else}<span>Wie im Buch</span>{/if}
        <span class="schiebt"><Knopf text="Zurücksetzen" symbol="rotate-left" klein frei gesperrt={!arbeit.geaendert} titel="Wieder das Listing aus dem Buch" onclick={onzuruecksetzen} /></span>
      </div>
    </div>
  {:else}
    <div class="inhalt">
      <pre class="konsole">{#if arbeit.lauf?.ausgabe}{arbeit.lauf.ausgabe.trimEnd()}{:else}<span class="leer">{arbeit.lauf ? "Keine Ausgabe" : "Noch kein Lauf"}</span>{/if}</pre>
      {#if arbeit.lauf?.fehler}<div class="meldung-lauf"><Symbol name="bug" /><span>{arbeit.lauf.fehler}{arbeit.lauf.fehlerzeile ? ` (Zeile ${arbeit.lauf.fehlerzeile})` : ""}</span></div>{/if}
    </div>
  {/if}
</section>
