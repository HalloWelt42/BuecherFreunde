<script lang="ts">
  // Debugger und Ausgabe unter dem Editor (BF-29, Entwurf ausfuehren.html): Steuerung des Appkerns in einer Zeile mit der
  // Wahl Debugger oder Ausgabe, Zeitleiste mit den Haltepunkten, Variablen (im Schritt geändert hervorgehoben), Aufrufe,
  // Ausgabe bis hier. Die Steuerung selbst ist die des Appkerns (lib/ausfuehren/arbeit.svelte.ts).
  import type { Ziel } from "appkern-oberflaeche/code";
  import { SPRACHNAMEN } from "../api/ausfuehren";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import type { Arbeit } from "./arbeit.svelte";

  let { arbeit, aufzeichnen }: { arbeit: Arbeit; aufzeichnen: boolean } = $props();

  const KNOEPFE: { ziel: Ziel; symbol: string; titel: string; trenner?: boolean }[] = [
    { ziel: "anfang", symbol: "backward-fast", titel: "Zum Anfang" },
    { ziel: "zurueckHalt", symbol: "backward", titel: "Zurück zum vorigen Haltepunkt" },
    { ziel: "zurueck", symbol: "backward-step", titel: "Einen Schritt zurück", trenner: true },
    { ziel: "hinein", symbol: "arrow-turn-down", titel: "Schritt hinein: die nächste Zeile, auch in eine Funktion" },
    { ziel: "ueber", symbol: "share", titel: "Schritt über: Funktionsaufrufe in einem Zug" },
    { ziel: "hinaus", symbol: "arrow-turn-up", titel: "Schritt hinaus: bis die Funktion zurückkehrt" },
    { ziel: "weiterHalt", symbol: "forward", titel: "Weiter bis zum nächsten Haltepunkt" },
    { ziel: "ende", symbol: "forward-fast", titel: "Zum Ende" },
  ];

  let s = $derived(arbeit.sitzung);
  let lauf = $derived(arbeit.lauf);
  let n = $derived(arbeit.schritte.length);
  let imDebugger = $derived(arbeit.reiter === "debugger");
  const rahmenName = (name: string) => (name === "Modul" ? "Modul" : `${name}()`);
  const anteil = (k: number) => `${(k / Math.max(1, n)) * 100}%`;

  let leiste: HTMLElement | undefined = $state();
  function klickLeiste(e: MouseEvent) {
    if (!leiste || !n) return;
    const r = leiste.getBoundingClientRect();
    arbeit.gehezu(Math.floor(((e.clientX - r.left) / r.width) * n));
  }
  function tasteLeiste(e: KeyboardEvent) {
    const ziel: Partial<Record<string, Ziel>> = { ArrowLeft: "zurueck", ArrowRight: "hinein", Home: "anfang", End: "ende" };
    const z = ziel[e.key];
    if (!z) return;
    e.preventDefault();
    arbeit.gehe(z);
  }
</script>

<div class="dbg-bereich">
  <div class="kopfzeile">
    <div class="segment" role="group" aria-label="Debugger oder Ausgabe">
      {#if aufzeichnen}<button type="button" aria-pressed={imDebugger} onclick={() => (arbeit.reiter = "debugger")}><Symbol name="bug" /> Debugger</button>{/if}
      <button type="button" aria-pressed={!imDebugger} onclick={() => (arbeit.reiter = "ausgabe")}><Symbol name="terminal" /> Ausgabe</button>
    </div>
    <span class="steuer schiebt" class:verborgen={!imDebugger}>
      {#each KNOEPFE as k (k.ziel)}
        <Knopf text={k.titel} symbol={k.symbol} nur gesperrt={!n || arbeit.ziel(k.ziel) === arbeit.i} onclick={() => arbeit.gehe(k.ziel)} />
        {#if k.trenner}<span class="trenner"></span>{/if}
      {/each}
    </span>
    <span class="schrittzahl zahl" class:verborgen={!imDebugger || !n}>Schritt {arbeit.i + 1}/{n}</span>
  </div>

  {#if imDebugger}
    <div class="seite">
      {#if s.laeuft}
        <p class="leise"><Symbol name="circle-notch" dreht /> Zeichne den Lauf auf ...</p>
      {:else if s.fehler}
        <div class="meldung-lauf"><Symbol name="triangle-exclamation" /><span>{s.fehler}</span></div>
      {:else if !lauf}
        <p class="leise">Debuggen zeichnet den Lauf auf: danach geht jeder Schritt vor und zurück, mit Variablen, Aufrufen und der Ausgabe bis dahin.</p>
      {/if}
      {#if lauf && !s.laeuft}
        {#if arbeit.veraltet}
          <div class="veraltet"><Symbol name="pen" /><span>Code geändert: die Aufzeichnung zeigt den alten Stand.</span><Knopf text="Neu" symbol="rotate-right" klein onclick={() => void s.neu(arbeit.code)} /></div>
        {/if}
        {#if n}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <div class="zeitleiste" bind:this={leiste} onclick={klickLeiste} onkeydown={tasteLeiste} role="slider" tabindex="0" aria-label="Schritt in der Zeitleiste" aria-valuemin={1} aria-valuemax={n} aria-valuenow={arbeit.i + 1} title="Alle Schritte; rot: Haltepunkte">
            <span style:width="{((arbeit.i + 1) / n) * 100}%"></span>
            {#each arbeit.treffer as k (k)}<i style:left={anteil(k + 0.5)}></i>{/each}
          </div>
          <div class="debug">
            <div class="feldchen">
              <h4>Variablen</h4>
              <dl class="werte">
                {#each arbeit.variablen as v (v.name)}<dt>{v.name}</dt><dd class="typ">{v.art}</dd><dd class:neu={v.neu} title={v.wert}>{v.wert}</dd>{/each}
              </dl>
            </div>
            <div class="rechts">
              <div class="feldchen">
                <h4>Aufrufe</h4>
                <ol class="stapel">
                  {#each arbeit.stapel as r, k (k)}
                    <li class:aktiv={k === 0}><code>{rahmenName(r.name)}</code><span>{k === 0 && arbeit.eintritt ? "wird aufgerufen" : r.zeile === null ? "" : `Zeile ${r.zeile}`}</span></li>
                  {/each}
                </ol>
              </div>
              <div class="feldchen">
                <h4>Ausgabe bis hier</h4>
                <pre class="konsole">{#if arbeit.ausgabeBisher.trim()}{arbeit.ausgabeBisher.trimEnd()}{:else}<span class="leer">(noch keine)</span>{/if}</pre>
              </div>
              {#if lauf.fehler && arbeit.i === n - 1}<div class="meldung-lauf"><Symbol name="bug" /><span>{lauf.fehler}{lauf.fehlerzeile ? ` (Zeile ${lauf.fehlerzeile})` : ""}</span></div>{/if}
            </div>
          </div>
        {/if}
        {#if lauf.gekuerzt}<p class="leise">Aufzeichnung nach {n} Schritten gekürzt; der Code lief trotzdem zu Ende.</p>{/if}
      {/if}
    </div>
  {:else}
    <div class="ausgabeseite">
      {#if s.laeuft}
        <p class="leise"><Symbol name="circle-notch" dreht /> Läuft in der Sandbox ...</p>
      {:else if s.fehler}
        <div class="meldung-lauf"><Symbol name="triangle-exclamation" /><span>{s.fehler}</span></div>
      {:else if lauf}
        {#if arbeit.veraltet}<p class="leise"><Symbol name="pen" /> Code geändert: Ausführen zeigt den neuen Stand.</p>{/if}
        <pre class="konsole">{#if lauf.ausgabe}{lauf.ausgabe.trimEnd()}{:else}<span class="leer">Keine Ausgabe</span>{/if}</pre>
        {#if lauf.fehler}<div class="meldung-lauf"><Symbol name="bug" /><span>{lauf.fehler}{lauf.fehlerzeile ? ` (Zeile ${lauf.fehlerzeile})` : ""}</span></div>{/if}
        {#if lauf.hinweise}<div class="hinweise"><Symbol name="circle-info" /><pre>{lauf.hinweise}</pre></div>{/if}
        {#if lauf.zeitueberschreitung}<p class="leise">Zeit überschritten: der Lauf wurde abgebrochen.</p>{/if}
        <p class="leise">Lief <span class="zahl">{Math.round(lauf.laufzeit_ms)}</span> ms mit {SPRACHNAMEN[arbeit.sprache]}{arbeit.laufFassung ? ` ${arbeit.laufFassung}` : ""} in der Sandbox der Codeschmiede.</p>
      {:else}
        <p class="leise">Ausführen schickt den Code in die Sandbox der Codeschmiede: ohne Netz, mit Grenzen für Zeit und Speicher.</p>
      {/if}
    </div>
  {/if}
</div>
