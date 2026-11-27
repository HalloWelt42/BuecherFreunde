<script lang="ts">
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { ladeOberflaeche, ladeServer, strenge, type Paket } from "./drittanbieter";

  const server = ladeServer();
  const oberflaeche = ladeOberflaeche();
  const lizenzliste = __LIZENZLISTE__;
</script>

{#snippet tafel(titel: string, liste: Promise<Paket[]>)}
  {#await liste}
    <Zustand art="laedt" text="{titel} wird geladen" />
  {:then pakete}
    <div class="weit">
      <table class="tabelle zuordnung">
        <caption>{titel}</caption>
        <thead><tr><th>Paket</th><th>Lizenz</th><th>Wofür</th></tr></thead>
        <tbody>
          {#each pakete as p (p.schluessel)}
            <tr><td>{#if p.adresse}<a href={p.adresse} target="_blank" rel="noopener">{p.name}</a>{:else}{p.name}{/if} <span class="leise zahl">{p.fassung}</span></td><td><span class="marke-text {strenge(p.lizenz)}">{p.lizenz}</span></td><td>{p.zweck}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:catch fehler}
    <Zustand art="fehler" text="{titel}: {fehler instanceof Error ? fehler.message : String(fehler)}" />
  {/await}
{/snippet}

<p>BücherFreunde steht unter der AGPL-3.0 und nutzt diese Pakete; jedes behält seine eigene Lizenz. Die Lizenztexte liegen bei: der Oberfläche in {lizenzliste}, dem Server in seinen Paketen.</p>
{@render tafel("Server", server)}
{@render tafel("Oberfläche", oberflaeche)}
<div class="reihe leise">
  <span class="lampe"><span class="led gut"></span>frei nutzbar (MIT, BSD, ISC, Apache, OFL, CC BY)</span>
  <span class="lampe"><span class="led warn"></span>schwaches Copyleft (LGPL, MPL)</span>
  <span class="lampe"><span class="led schlecht"></span>starkes Copyleft (GPL, AGPL)</span>
</div>
