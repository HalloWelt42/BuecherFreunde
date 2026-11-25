<script lang="ts">
  import { oberflaeche, server, strenge, type Paket } from "./drittanbieter";
</script>

{#snippet tafel(titel: string, pakete: Paket[])}
  <div class="weit">
    <table class="tabelle zuordnung">
      <caption>{titel}</caption>
      <thead><tr><th>Paket</th><th>Lizenz</th><th>Wofür</th></tr></thead>
      <tbody>
        {#each pakete as p (p.name)}
          <tr><td><a href={p.adresse} target="_blank" rel="noopener">{p.name}</a></td><td><span class="marke-text {strenge(p.lizenz)}">{p.lizenz}</span></td><td>{p.zweck}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{/snippet}

<p>BücherFreunde nutzt diese freien Pakete. Die Lizenztexte stehen in den Quellen der Pakete.</p>
{@render tafel("Server", server)}
{@render tafel("Oberfläche", oberflaeche)}
<div class="reihe leise">
  <span class="lampe"><span class="led gut"></span>frei nutzbar (MIT, BSD, Apache, OFL)</span>
  <span class="lampe"><span class="led warn"></span>schwaches Copyleft (LGPL)</span>
  <span class="lampe"><span class="led schlecht"></span>starkes Copyleft (GPL, AGPL)</span>
</div>
