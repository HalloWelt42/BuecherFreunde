<script lang="ts">
  // Lücken einer Sammlung bearbeiten (BF-75): Platzhalter an oder aus, je Sprache die Zahl der Bände (aus den Quellen, eigene
  // Angabe oder leer für keine Zahl), ausgeblendete Bände zurückholen. Gespeichert wird mit der Sammlung; Zurückholen gilt
  // sofort.
  import { holeLueckeZurueck, ladeLuecken, type Ausgeblendet, type Gesamtangabe, type Sammlungsluecken } from "../../lib/api/luecken";
  import { gesamtAus, gesamtfeld, herkunftstext } from "../../lib/luecken";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { ich } from "../../lib/stand/ich.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Flagge from "../../lib/teile/Flagge.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Schalter from "../../lib/teile/Schalter.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { sammlung }: { sammlung: number } = $props();

  let luecken = $state<Sammlungsluecken | null>(null);
  let an = $state(true);
  let felder = $state<Record<string, string>>({});
  /** Sprachen, die wieder der Zahl der Quellen folgen sollen */
  let zurQuelle = $state<string[]>([]);
  let holt = $state("");
  let darf = $derived(ich.darf("bearbeiten"));

  function nimm(l: Sammlungsluecken, mitFeldern: boolean) {
    luecken = l;
    if (!mitFeldern) return;
    an = l.an;
    felder = Object.fromEntries(l.reihen.map((r) => [r.sprache, gesamtfeld(r)]));
  }

  $effect(() => {
    ladeLuecken(sammlung).then((l) => nimm(l, true)).catch(() => (luecken = null));
  });

  /** Was sich geändert hat, für den PATCH beim Speichern; null: nichts. Wirft bei einer Zahl, die nicht geht. */
  export function aenderung(): { an?: boolean; gesamt?: Gesamtangabe[] } | null {
    if (!luecken || !darf) return null;
    const gesamt = luecken.reihen
      .map((r): Gesamtangabe | null => (zurQuelle.includes(r.sprache) ? { sprache: r.sprache, wahl: "quelle" } : gesamtAus(r, felder[r.sprache] ?? "")))
      .filter((g): g is Gesamtangabe => !!g);
    const neu = { ...(an !== luecken.an ? { an } : {}), ...(gesamt.length ? { gesamt } : {}) };
    return Object.keys(neu).length ? neu : null;
  }

  /** Zur Zahl der Quellen zurück: das Feld zeigt sie, gespeichert wird mit der Sammlung */
  function nimmQuelle(sprache: string, zahl: number) {
    felder = { ...felder, [sprache]: String(zahl) };
    zurQuelle = [...zurQuelle, sprache];
  }

  function setze(sprache: string, wert: unknown) {
    felder = { ...felder, [sprache]: wert === null || wert === undefined ? "" : String(wert) };
    zurQuelle = zurQuelle.filter((s) => s !== sprache);
  }

  async function zurueckholen(a: Ausgeblendet) {
    holt = `${a.sprache}:${a.nummer}`;
    try {
      nimm(await holeLueckeZurueck(sammlung, a.sprache, a.nummer), false);
      melde.gut(`Band ${a.nummer}, ${a.name}, steht wieder als Lücke im Regal`);
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht zurückgeholt");
    } finally {
      holt = "";
    }
  }
</script>

{#if luecken}
  <section class="lueckenteil">
    <h3><Symbol name="puzzle-piece" />Lücken</h3>
    <div class="zeile2"><span>Platzhalter im Regal<small>fehlende Bände als blasse Umschläge</small></span><Schalter {an} name="Platzhalter im Regal" gesperrt={!darf} onwahl={(w) => (an = w)} /></div>
    {#if luecken.reihen.length}
      <div class="feld">
        <span>Bände je Sprache</span>
        {#each luecken.reihen as r (r.sprache)}
          {@const h = herkunftstext(r)}
          <div class="gesamtzeile">
            {#if r.sprache}<Flagge sprache={r.sprache} groesse="1.25rem" />{:else}<span></span>{/if}
            <span>{r.name}</span>
            <input class="eingabe zahl" type="number" min="1" max="9999" step="1" inputmode="numeric" aria-label="Bände auf {r.name}" disabled={!darf} bind:value={() => felder[r.sprache] ?? "", (w) => setze(r.sprache, w)} />
            <span>
              <span class={h.eigen ? "marke-text info" : "leise"} title={r.nachschlagen.quelle_name ? `${r.nachschlagen.quelle_name}, gefragt nach ${r.nachschlagen.reihe}` : undefined}><Symbol name={h.symbol} />{h.text}</span>
              {#if h.eigen && r.quelle_gesamt && darf && !zurQuelle.includes(r.sprache)}<Knopf text="Zahl der Quellen nehmen ({r.quelle_gesamt})" symbol="book-atlas" nur klein frei onclick={() => nimmQuelle(r.sprache, r.quelle_gesamt!)} />{/if}
            </span>
          </div>
        {/each}
        <span class="leise">Leer: nur Lücken zwischen vorhandenen Bänden</span>
      </div>
    {/if}
    {#if luecken.ausgeblendet.length}
      <div class="feld">
        <span>Ausgeblendet</span>
        {#each luecken.ausgeblendet as a (`${a.sprache}:${a.nummer}`)}
          <div class="zeile2"><span>Band {a.nummer}, {a.name}{#if a.titel}: {a.titel}{/if}<small>{a.grund_text}</small></span><Knopf text="Zurückholen" symbol="rotate-left" klein gesperrt={!darf} laeuft={holt === `${a.sprache}:${a.nummer}`} onclick={() => void zurueckholen(a)} /></div>
        {/each}
      </div>
    {/if}
  </section>
{/if}
