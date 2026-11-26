<script lang="ts">
  // Regeln einer Kategorie (BF-69): je Art eine Zeile mit ihren Werten und den Treffern im Bestand; ein Treffer reicht.
  // Treffer stehen nur an Zeilen, die so gespeichert sind, wie der Server sie gezählt hat.
  import { untrack } from "svelte";
  import { beiEsc } from "../../../lib/flucht";
  import { anzahl, zahl } from "../../../lib/format";
  import { REGELARTEN } from "../../../lib/katalog";
  import Chip from "../../../lib/teile/Chip.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import type { Kategorieregeln, Kategorietreffer, Regelart } from "../../../lib/typen";

  interface Eigenschaften {
    regeln: Kategorieregeln;
    /** Wie die Regeln gespeichert sind; daran hängen die Treffer */
    gespeichert: Kategorieregeln;
    treffer: Kategorietreffer | null;
    onaendern: (regeln: Kategorieregeln) => void;
  }
  let { regeln, gespeichert, treffer, onaendern }: Eigenschaften = $props();

  let gezeigt = $state<Regelart[]>(untrack(() => REGELARTEN.map(([a]) => a).filter((a) => regeln[a].length)));
  let neuIn = $state<Regelart | "">("");
  let wort = $state("");
  /** Die fehlenden Arten stehen zur Wahl; im Fenster gleich in der Zeile, ein schwebendes Feld läge unter dem Fenster */
  let artwahl = $state(false);

  let zeilen = $derived(REGELARTEN.filter(([a]) => gezeigt.includes(a)));
  let fehlend = $derived(REGELARTEN.filter(([a]) => !gezeigt.includes(a)));
  let unveraendert = $derived(REGELARTEN.every(([a]) => gleich(regeln[a], gespeichert[a])));

  const gleich = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((w, n) => w === b[n]);
  const trefferVon = (a: Regelart) => (gleich(regeln[a], gespeichert[a]) ? treffer?.regeln.find((r) => r.art === a)?.treffer : undefined);

  // Esc verwirft erst den neuen Wert, dann schließt das Fenster
  $effect(() => {
    if (neuIn)
      return beiEsc(() => {
        wort = "";
        neuIn = "";
      });
  });

  const setze = (a: Regelart, werte: string[]) => onaendern({ ...regeln, [a]: werte });

  function fuegeHinzu(a: Regelart) {
    const w = wort.trim();
    if (w && !regeln[a].includes(w)) setze(a, [...regeln[a], w]);
    wort = "";
  }

  function entferneRegel(a: Regelart) {
    setze(a, []);
    gezeigt = gezeigt.filter((x) => x !== a);
    if (neuIn === a) neuIn = "";
  }

  function neueRegel(a: Regelart) {
    artwahl = false;
    gezeigt = [...gezeigt, a];
    neuIn = a;
  }

  function oeffne(a: Regelart) {
    wort = "";
    neuIn = a;
  }

  const fokus = (feld: HTMLInputElement) => feld.focus();
</script>

<div class="regeln">
  {#each zeilen as [art, name, symbol] (art)}
    {@const n = trefferVon(art)}
    <div class="regelzeile">
      <span class="art"><Symbol name={symbol} klasse="leise" />{name}</span>
      <span class="werte">
        {#each regeln[art] as w (w)}<Chip text={w} titel="{w} entfernen" onclick={() => setze(art, regeln[art].filter((x) => x !== w))}><Symbol name="xmark" klasse="leise" /><span class="nur-vorlesen">entfernen</span></Chip>{/each}
        {#if neuIn === art}
          <!-- Ein eigenes Formular im Formular des Fensters geht nicht; Enter fängt das Feld selbst ab -->
          <input class="eingabe regelwert" aria-label="Neuer Wert: {name}" maxlength="100" bind:value={wort} use:fokus
            onkeydown={(e) => { if (e.key === "Enter") { e.preventDefault(); fuegeHinzu(art); } }} onblur={() => { fuegeHinzu(art); neuIn = ""; }} />
        {:else}
          <Chip text="Wert dazu" symbol="plus" nur onclick={() => oeffne(art)} />
        {/if}
      </span>
      <span class="regeltreffer zahl">{n === undefined ? "" : zahl(n)}</span>
      <Knopf text="Regel entfernen" symbol="trash" nur klein frei onclick={() => entferneRegel(art)} />
    </div>
  {:else}<p class="leise">Noch keine Regel: dann ordnet nur die KI ein.</p>{/each}
</div>
<div class="reihe">
  {#if fehlend.length}
    <Knopf text="Regel" symbol="plus" klein aufgeklappt={artwahl} onclick={() => (artwahl = !artwahl)} />
    {#if artwahl}{#each fehlend as [art, name, symbol] (art)}<Chip text={name} {symbol} onclick={() => neueRegel(art)} />{/each}{/if}
  {/if}
  {#if treffer && unveraendert}<span class="leise zahl">zusammen {anzahl(treffer.zusammen, "Buch", "Bücher")}, dazu {anzahl(treffer.ki_vorschlaege, "Vorschlag", "Vorschläge")} der KI</span>{/if}
</div>
