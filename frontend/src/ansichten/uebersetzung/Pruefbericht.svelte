<script lang="ts">
  // Prüfbericht einer Übersetzung (BF-71, Entwurf Abschnitt 4): die Zahlen, darunter jede offene Stelle zum Entscheiden.
  // Die Zahlen bleiben stehen, nur die Stellen rollen.
  import { untrack } from "svelte";
  import { holeBericht } from "../../lib/api/uebersetzung";
  import { uebersetzungen } from "../../lib/stand/uebersetzungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { berichtsmarken } from "../../lib/uebersetzung/texte";
  import type { Bericht } from "../../lib/uebersetzung/typen";
  import { Buchuebersetzung } from "./fassung.svelte";
  import Offenestelle from "./Offenestelle.svelte";

  let { params }: { params: Record<string, string> } = $props();

  const bezug = new Buchuebersetzung(untrack(() => Number(params.id)));
  let bericht = $state<Bericht | null>(null);
  let fehler = $state("");

  async function hole() {
    const f = bezug.deutsch;
    if (!f) return;
    try {
      bericht = await holeBericht(f.id);
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void bezug.laden().then(hole));

  /** Erledigt: die Stelle geht aus der Liste, die Zahlen kommen neu; "Neu übersetzen" stößt den Lauf an */
  function erledigt(kennung: string) {
    if (bericht) bericht = { ...bericht, offen: bericht.offen.filter((o) => o.kennung !== kennung) };
    uebersetzungen.angestossen();
    void hole();
  }
</script>

<div class="werkzeug">
  <Knopf text="Zum Buch" symbol="arrow-left" klein href="/book/{bezug.id}" />
  <h1>Prüfbericht</h1>
  {#if bezug.buch}<span class="leise">{bezug.buch.title}</span>{/if}
</div>

<div class="inhalt rollen">
  {#if bezug.fehler || (fehler && !bericht)}
    <Zustand art="fehler" text={bezug.fehler || fehler} onerneut={() => void bezug.laden().then(hole)} />
  {:else if bezug.geladen && !bezug.deutsch}
    <Zustand text="Dieses Buch wird noch nicht übersetzt."><Knopf text="Zum Buch" symbol="arrow-left" klein href="/book/{bezug.id}" /></Zustand>
  {:else if !bericht || !bezug.deutsch}
    <Zustand art="laedt" text="Prüfbericht wird geladen" />
  {:else}
    {@const fassung = bezug.deutsch.id}
    <div class="fuellt">
      <div class="reihe">{#each berichtsmarken(bericht.zahlen) as m (m.ton)}<span class="marke-text {m.ton}"><Symbol name={m.symbol} />{m.text}</span>{/each}</div>
      <div class="berichtsliste rollen">
        {#each bericht.offen as stelle (stelle.kennung)}
          <Offenestelle {stelle} {fassung} onerledigt={() => erledigt(stelle.kennung)} />
        {:else}
          <p class="leise">Keine offenen Stellen.</p>
        {/each}
      </div>
    </div>
  {/if}
</div>
