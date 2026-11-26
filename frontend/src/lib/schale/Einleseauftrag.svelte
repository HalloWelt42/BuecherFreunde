<script lang="ts">
  // Einlesen aus Ordnern als ein Auftrag: Einträge der Annahme mit Quelle Ordner oder externe Sammlung
  import { annahme } from "../stand/annahme.svelte";
  import { schale } from "../stand/schale.svelte";
  import type { Sammellage } from "../annahme/sammlung";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";

  let s = $derived(annahme.einlesen);
  let nach = (lage: Sammellage) => s.eintraege.filter((e) => s.lagen.get(e.id) === lage);
  let fehler = $derived(nach("fehler").slice(0, 5));
  let wartend = $derived(nach("wartet").slice(0, 3));
  let zuletzt = $derived(nach("fertig").slice(-3).reverse());
</script>

<div class="auftrag">
  <b>Dateien einlesen</b>
  <Balken anteil={s.gesamt ? (s.imRegal + s.da) / s.gesamt : 0} name="Dateien einlesen" />
  <span class="leise zahl">{s.imRegal} von {s.gesamt} im Regal{s.da ? `, ${s.da} gab es schon` : ""}{s.gescheitert ? `, ${s.gescheitert} gescheitert` : ""}</span>
  {#if s.aktuell}<span class="marke-text info">{s.aktuell.name}: {s.aktuell.text || "läuft"}</span>{/if}
  {#each fehler as a (a.id)}<span class="marke-text schlecht">{a.name}: {a.text || "gescheitert"}</span>{/each}
  {#each wartend as a (a.id)}<span class="leise">{a.name} wartet</span>{/each}
  {#if s.wartend > wartend.length}<span class="leise zahl">und {s.wartend - wartend.length} weitere</span>{/if}
  {#each zuletzt as a (a.id)}
    <span class="reihe"><span class="marke-text gut name">{a.name}</span>{#if a.buch_id}<Knopf text="Anzeigen" symbol="arrow-right" klein frei href="/book/{a.buch_id}" onclick={() => schale.schliesseAlles()} />{/if}</span>
  {/each}
</div>

<style>
  .auftrag {
    display: grid;
    gap: 0.375rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--linie);
    overflow-wrap: anywhere;
  }
  .name {
    flex: 1;
    min-width: 0;
  }
</style>
