<script lang="ts">
  // Server und KI werden beim Öffnen gefragt, die Quellen nicht: ihr Stand ist gemerkt. "Neu prüfen" fragt nur die gewählte.
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { quellen } from "../../lib/stand/quellen.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { alsDienst, pruefeDienste, type Dienst, type Zuordnung } from "./dienste";

  let liste = $state<Dienst[]>([]);
  let gewaehlt = $state("server");
  let prueft = $state(false);
  let dienst = $derived(liste.find((d) => d.kennung === gewaehlt) ?? liste[0]);

  async function lade() {
    prueft = true;
    try {
      await quellen.laden();
      liste = await pruefeDienste(quellen.liste);
    } catch (e) {
      melde.schlecht(e, "Dienste nicht geprüft");
    }
    prueft = false;
  }

  async function pruefe(d: Dienst) {
    if (!d.quelle) return void lade();
    prueft = true;
    try {
      const neu = await quellen.pruefe(d.kennung);
      if (neu) liste = liste.map((x) => (x.kennung === neu.kennung ? alsDienst(neu) : x));
    } catch (e) {
      melde.schlecht(e, "Nicht geprüft");
    }
    prueft = false;
  }

  $effect(() => void lade());
</script>

{#snippet tabelle(titel: string, links: string, rechts: string, zeilen: Zuordnung[])}
  <div class="weit">
    <table class="tabelle zuordnung">
      <caption>{titel}</caption>
      <thead><tr><th>{links}</th><th>{rechts}</th></tr></thead>
      <tbody>{#each zeilen as [von, nach] (von)}<tr><td><code>{von}</code></td><td>{nach}</td></tr>{/each}</tbody>
    </table>
  </div>
{/snippet}

{#if !liste.length}
  <Zustand art="laedt" text="Dienste werden geprüft" />
{:else if dienst}
  <div class="reihe" role="group" aria-label="Dienste">
    {#each liste as d (d.kennung)}
      <Chip symbol={d.symbol} gedrueckt={d.kennung === dienst.kennung} titel={d.wort} onclick={() => (gewaehlt = d.kennung)}>{d.name} <span class="led {d.stand}"></span></Chip>
    {/each}
    <span class="schiebt"><Knopf text="Neu prüfen" symbol="arrows-rotate" klein laeuft={prueft} titel={dienst.quelle ? "Fragt diese Quelle jetzt, höchstens einmal in der Minute" : undefined} onclick={() => void pruefe(dienst)} /></span>
  </div>
  <div class="dienst">
    <p><span class="marke-text {dienst.stand === 'aus' ? 'leise' : dienst.stand}">{dienst.wort}</span>{#if dienst.text}{" "}<span class="leise">{dienst.text}</span>{/if}</p>
    {#if dienst.zahlen}<p class="leise klein zahl">{dienst.zahlen}</p>{/if}
    {#if dienst.adresse}<code class="pfad">{dienst.adresse}</code>{/if}
    <p class="klein">{dienst.beschreibung}</p>
    {#if dienst.felder.length}{@render tabelle("Welche Felder daraus werden", "Feld der Quelle", "Feld im Buch", dienst.felder)}{/if}
    {#if dienst.autoren}
      {@render tabelle("Autoren", "Quelle", "Ziel", dienst.autoren)}
      <p class="leise">{dienst.konfidenz}</p>
    {/if}
    {#if dienst.roh}
      <div class="reihe rohfelder"><span class="leise">Dazu als Rohdaten:</span>{#each dienst.roh as feld (feld)}<code>{feld}</code>{/each}</div>
    {/if}
  </div>
{/if}
