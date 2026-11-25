<script lang="ts">
  import { auftraege } from "../stand/auftraege.svelte";
  import { schale } from "../stand/schale.svelte";
  import Balken from "../teile/Balken.svelte";
  import Knopf from "../teile/Knopf.svelte";

  let z = $derived(auftraege.zaehler);
  let fertig = $derived(z.fertig + z.duplikat);
  let nach = (stand: string) => auftraege.aufgaben.filter((a) => a.status === stand);
  let laufend = $derived(nach("verarbeite"));
  let fehler = $derived(nach("fehler").slice(0, 5));
  let wartend = $derived(nach("wartend"));
  let zuletzt = $derived(nach("fertig").slice(-3).reverse());
</script>

<div class="auftrag">
  <b>Dateien einlesen</b>
  <Balken anteil={z.gesamt ? fertig / z.gesamt : 0} name="Dateien einlesen" />
  <span class="leise zahl">{z.fertig} von {z.gesamt} im Regal{z.duplikat ? `, ${z.duplikat} gab es schon` : ""}{z.fehler ? `, ${z.fehler} gescheitert` : ""}</span>
  {#each laufend as a (a.id)}<span class="marke-text info">{a.filename}: {a.current_step || "läuft"}, {a.progress_percent} %</span>{/each}
  {#each fehler as a (a.id)}<span class="marke-text schlecht">{a.filename}: {a.error || "gescheitert"}</span>{/each}
  {#each wartend.slice(0, 3) as a (a.id)}<span class="leise">{a.filename} wartet</span>{/each}
  {#if wartend.length > 3}<span class="leise zahl">und {wartend.length - 3} weitere</span>{/if}
  {#each zuletzt as a (a.id)}
    <span class="reihe"><span class="marke-text gut name">{a.filename}</span>{#if a.book_id}<Knopf text="Anzeigen" symbol="arrow-right" klein frei href="/book/{a.book_id}" onclick={() => schale.schliesseAlles()} />{/if}</span>
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
