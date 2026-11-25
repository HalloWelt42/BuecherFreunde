<script lang="ts">
  // Nur Bericht: öffnet jede Datei einmal und zeigt, was sich nicht lesen lässt. Bereinigt wird nie von selbst.
  import { formatName, groesse, zahl } from "../../lib/format";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { vorgaenge } from "./vorgaenge.svelte";

  let p = $derived(vorgaenge.pruefung);
</script>

<p class="klein">Öffnet jede Buchdatei einmal und meldet, was fehlt, leer ist oder sich nicht lesen lässt. Es ändert sich nichts.</p>
<div class="reihe"><Knopf text="Dateien prüfen" symbol="stethoscope" klein laeuft={vorgaenge.laeuft.dateien} onclick={() => void vorgaenge.pruefe()} /></div>
{#if p}
  <p class="marke-text {p.defekt ? 'warn' : 'gut'}">{zahl(p.geprueft)} Dateien geprüft, {p.defekt ? `${zahl(p.defekt)} auffällig` : "alles in Ordnung"}</p>
  {#if p.eintraege.length}
    <div class="weit">
      <table class="tabelle zuordnung">
        <thead><tr><th>Buch</th><th>Datei</th><th>Grund</th></tr></thead>
        <tbody>
          {#each p.eintraege as d (d.id)}
            <tr><td><a href="/book/{d.id}">{d.titel}</a>{#if d.autor}<br /><span class="leise">{d.autor}</span>{/if}</td><td><code class="pfad">{d.dateiname}</code><br /><span class="leise zahl">{formatName(d.format)}, {groesse(d.groesse)}</span></td><td>{d.grund}</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}
