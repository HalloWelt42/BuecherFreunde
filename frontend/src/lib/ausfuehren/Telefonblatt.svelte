<script lang="ts">
  // Ausführen am Telefon (BF-29): ein Blatt unten über der Tafel, ohne Editor. Ausführen zeichnet jeden Lauf auf; fünf
  // gleich hohe Tasten ohne Beschriftung; der Code nur lesend, fünf Zeilen um die gezeigte, darunter die Werte; zweiter
  // Reiter die Ausgabe. Ein Tipp auf die Nummer einer Zeile setzt oder löscht den Haltepunkt.
  import type { Ziel } from "appkern-oberflaeche/code";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import type { Arbeit } from "./arbeit.svelte";
  import { faerbeZeilen } from "./zeilen";

  let { arbeit, name, kann, fassung, ed, onzurstelle, onschliessen }: { arbeit: Arbeit; name: string; kann: boolean; fassung: string; ed: string; onzurstelle: () => void; onschliessen: () => void } = $props();

  const UMKREIS = 2;
  const GRIFFE: { ziel: Ziel; symbol: string; titel: string }[] = [
    { ziel: "zurueckHalt", symbol: "backward", titel: "Zurück zum vorigen Haltepunkt" },
    { ziel: "zurueck", symbol: "backward-step", titel: "Schritt zurück" },
    { ziel: "hinein", symbol: "forward-step", titel: "Schritt vor" },
    { ziel: "weiterHalt", symbol: "forward", titel: "Weiter bis zum nächsten Haltepunkt" },
  ];

  let wahl = $state<"code" | "ausgabe">("code");
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

<section class="schwebefenster glas dicht blatt-sheet" aria-label="Ausführen" data-ed={ed} data-eigene-tasten>
  <div class="zug"></div>
  <header>
    <div class="titel"><b>{name}</b><span class="zahl">{n ? `Schritt ${arbeit.i + 1} von ${n}${jetzt ? ` · Zeile ${jetzt}` : ""}` : arbeit.sitzung.laeuft ? "Zeichne den Lauf auf ..." : "Noch kein Lauf"}</span></div>
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
  {:else}
    <div class="inhalt">
      <pre class="konsole">{#if arbeit.lauf?.ausgabe}{arbeit.lauf.ausgabe.trimEnd()}{:else}<span class="leer">{arbeit.lauf ? "Keine Ausgabe" : "Noch kein Lauf"}</span>{/if}</pre>
      {#if arbeit.lauf?.fehler}<div class="meldung-lauf"><Symbol name="bug" /><span>{arbeit.lauf.fehler}{arbeit.lauf.fehlerzeile ? ` (Zeile ${arbeit.lauf.fehlerzeile})` : ""}</span></div>{/if}
    </div>
  {/if}
</section>
