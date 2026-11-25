<script lang="ts">
  // Eingangsordner in der Kellerwolke: Abgelegtes kommt von selbst in die Bibliothek. Hier steht, was noch darin liegt und warum.
  import { lageFuer } from "../../../lib/annahme/zeilen";
  import { ladeEingangsordner, nimmEingangsordnerAuf, type Eingangsordner } from "../../../lib/api/annahme";
  import { anzahl, groesse, zahl } from "../../../lib/format";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { ordner, onstand }: { ordner: Eingangsordner; onstand: (o: Eingangsordner) => void } = $props();

  const HOECHSTENS = 60;
  let sieht = $state(false);
  let fehler = $state("");

  async function siehNach() {
    sieht = true;
    fehler = "";
    try {
      const { neu } = await nimmEingangsordnerAuf();
      if (neu) melde.gut(`${anzahl(neu, "neue Datei", "neue Dateien")} gefunden`);
      else melde.info("Nichts Neues im Eingangsordner");
      onstand(await ladeEingangsordner());
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      sieht = false;
    }
  }
</script>

<Karte titel="Eingangsordner" symbol="folder-open">
  <p>Was du dort ablegst, kommt binnen einer Minute in die Bibliothek und zieht dabei um.</p>
  <div class="reihe">
    <span class="leise pfad"><Symbol name="cloud" /> {ordner.pfad}</span>
    <span class="schiebt"><Knopf text="Jetzt nachsehen" symbol="arrows-rotate" klein laeuft={sieht} onclick={() => void siehNach()} /></span>
  </div>
  {#if fehler}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />{fehler}</p>{/if}
  {#if ordner.dateien.length}
    <ul class="dateien">
      {#each ordner.dateien.slice(0, HOECHSTENS) as d, n (n)}
        {@const lage = lageFuer(d.stand)}
        <li><span class="name">{d.name}</span><span class="leise zahl">{groesse(d.groesse)}</span><span class="marke-text {lage.ton}"><Symbol name={lage.symbol} />{d.text}</span>{#if d.buch_id}<Knopf text="Buch öffnen" symbol="book-open" klein href="/book/{d.buch_id}" />{/if}</li>
      {/each}
    </ul>
    {#if ordner.dateien.length > HOECHSTENS}<p class="leise zahl">und {zahl(ordner.dateien.length - HOECHSTENS)} weitere</p>{/if}
  {:else}
    <p class="leise">Der Ordner ist leer.</p>
  {/if}
</Karte>

<style>
  .pfad {
    overflow-wrap: anywhere;
  }
  .dateien {
    display: grid;
    max-height: 18rem;
    overflow: auto;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.125rem 0.75rem;
    align-items: center;
    padding: 0.375rem 0;
    border-top: 1px solid var(--linie);
  }
  .name {
    flex: 1 1 12rem;
    min-width: 0;
    overflow-wrap: anywhere;
  }
</style>
