<script lang="ts">
  // Abgleich mit dem Lexikon: Schalter, Fortschritt, Ergebnisse
  import { zahl } from "../../lib/format";
  import { autorenabgleich as abgleich } from "../../lib/stand/autorenabgleich.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { sicherheit } from "./angaben";

  let { onzu }: { onzu: () => void } = $props();
  let offen = $derived(abgleich.fertig || abgleich.grund);

  function schliesse() {
    abgleich.schliesse();
    onzu();
  }
</script>

<Karte titel="Lexikon abgleichen" symbol="arrows-rotate">
  {#snippet neben()}
    {#if abgleich.laeuft}
      <Knopf text="Anhalten" symbol="stop" klein onclick={() => void abgleich.halte()} />
    {:else}
      <Knopf text="Schließen" symbol="xmark" nur klein frei onclick={schliesse} />
    {/if}
  {/snippet}

  {#if abgleich.laeuft}
    <Balken anteil={abgleich.anteil} name="Abgleich der Autoren" />
    <p class="leise zahl">{abgleich.gesamt ? `${zahl(abgleich.stelle)} von ${zahl(abgleich.gesamt)}` : "Wird vorbereitet"}{abgleich.name ? `, gerade ${abgleich.name}` : ""}. Der Auftrag läuft weiter, auch auf anderen Seiten.</p>
  {:else if offen}
    {#if abgleich.grund}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />{abgleich.grund}</p>{/if}
    {#if abgleich.fertig && abgleich.gesamt}<p>{abgleich.abgebrochen ? "Angehalten" : "Fertig"} nach {zahl(abgleich.stelle)} von {zahl(abgleich.gesamt)} Autoren.</p>
    {:else if abgleich.fertig && !abgleich.grund}<p>Alle Autoren haben schon einen Eintrag, es gab nichts zu tun.</p>{/if}
  {:else}
    <p>Sucht zu jedem Autor den passenden Eintrag in Normdatei und Lexikon, zuerst über die ISBN seiner Bücher. Sichere Treffer werden auf Wunsch gleich übernommen, alle anderen stehen danach hier zur Auswahl. Die Quellen werden dabei schonend gefragt; macht eine Pause, hält der Abgleich an.</p>
  {/if}

  {#if abgleich.ergebnisse.length}
    <p class="zahl">{abgleich.zusammenfassung}</p>
    {#if abgleich.gefunden.length}
      <div class="abgleichliste">
        {#each abgleich.gefunden as e (e.autor)}
          {@const s = sicherheit(e.vorschlag?.konfidenz)}
          <a href="/author/{e.autor}"><b>{e.name}</b><span class="leise">{e.vorschlag?.name ?? ""}</span><span><span class="marke-text {s.ton}">{s.wort}{e.vorschlag?.score ? `, ${e.vorschlag.score} Punkte` : ""}</span>{#if e.uebernommen}<span class="marke-text gut"><Symbol name="check" />übernommen</span>{:else if e.grund && e.grund !== "nicht sicher genug"}<span class="leise">{e.grund}</span>{/if}</span></a>
        {/each}
      </div>
    {/if}
    {#if abgleich.gescheitert.length}
      <ul class="gescheitert">{#each abgleich.gescheitert.slice(0, 5) as e (e.autor)}<li class="marke-text schlecht">{e.name}: {e.fehler}</li>{/each}</ul>
      {#if abgleich.gescheitert.length > 5}<p class="leise">und {abgleich.gescheitert.length - 5} weitere</p>{/if}
    {/if}
  {/if}

  {#if !abgleich.laeuft}
    <div class="reihe">
      <Haekchen text="Nur Autoren ohne Eintrag" an={abgleich.nurOhneEintrag} onwahl={(an) => (abgleich.nurOhneEintrag = an)} />
      <Haekchen text="Sichere Treffer selbst übernehmen" an={abgleich.sichereUebernehmen} onwahl={(an) => (abgleich.sichereUebernehmen = an)} />
      <span class="schiebt"><Knopf text={offen ? "Noch einmal starten" : "Abgleich starten"} symbol="play" haupt klein onclick={() => abgleich.starte()} /></span>
    </div>
  {/if}
</Karte>

<style>
  .gescheitert {
    display: grid;
    gap: 0.25rem;
  }
</style>
