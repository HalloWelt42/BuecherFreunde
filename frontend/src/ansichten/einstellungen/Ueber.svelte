<script lang="ts">
  import { OBERFLAECHE_FASSUNG } from "../../lib/fassung.svelte";
  import Logo from "../../lib/schale/Logo.svelte";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
</script>

<div class="ueber">
  <span class="symbol"><Logo /></span>
  <div>
    <b>BücherFreunde</b>
    <dl class="angaben">
      <dt>Oberfläche</dt><dd class="zahl">{OBERFLAECHE_FASSUNG}</dd>
      <dt>Server</dt><dd class="zahl">{verbindungen.fassung || "keine Angabe"}</dd>
      {#if verbindungen.neueFassung}<dt>Veröffentlicht</dt><dd><span class="marke-text info zahl">{verbindungen.neueFassung} steht bereit</span></dd>{/if}
    </dl>
    <div class="reihe"><Knopf text="Danke sagen" symbol="heart" klein href="/danke" /></div>
  </div>
</div>
