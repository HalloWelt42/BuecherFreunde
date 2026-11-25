<script lang="ts">
  import { beispiele } from "./suchsprache";
</script>

<div class="platte karte">
  <dl class="angaben">{#each beispiele as [muster, sinn] (muster)}<dt><code>{muster}</code></dt><dd>{sinn}</dd>{/each}</dl>
  <p class="leise">Alles lässt sich kombinieren: <code>"der Ring" autor:Wagner format:epub</code></p>
</div>

<style>
  code {
    font-family: var(--codeschrift);
    font-size: 0.875rem;
    font-variant-ligatures: none;
    color: var(--tinte);
    overflow-wrap: anywhere;
  }
</style>
