<script lang="ts">
  // Fortschritt des Assistenten: Überschrift des Schritts, "n von m" und die Stationen mit ihren Namen; übersprungene gestrichelt
  import type { Schritt } from "../../lib/api/einrichtung";
  import { fortschritt, schritttitel, STATIONSWORT, zeigtPflicht, type Lauf } from "../../lib/einrichtung/ablauf";

  let { lauf, schritte, schritt }: { lauf: Lauf; schritte: Schritt[]; schritt: Schritt } = $props();

  let f = $derived(fortschritt(lauf, schritte, schritt.schluessel));
  let spalten = $derived(`repeat(${f.stationen.length}, minmax(0, 1fr))`);
  let beschreibung = $derived(f.stationen.map((s) => `${s.name} ${STATIONSWORT[s.art]}`).join(", "));
</script>

<div class="ew-fortschritt">
  <div class="ew-schrittkopf">
    <h2>{schritttitel(lauf, schritt.schluessel)}</h2>
    {#if zeigtPflicht(schritte, schritt)}<span class="katalogmarke">Pflicht</span>{/if}
    <span class="leise zahl">{f.nummer ? `${f.nummer} von ${f.stationen.length}` : "fertig"}</span>
  </div>
  {#if f.stationen.length}
    <div class="weg" style:--p="100%" style:grid-template-columns={spalten} role="img" aria-label={beschreibung}>
      {#each f.stationen as s (s.schluessel)}<span class={s.art} title="{s.name}: {STATIONSWORT[s.art]}"></span>{/each}
    </div>
    <div class="legende ew-schritte" style:grid-template-columns={spalten} aria-hidden="true">
      {#each f.stationen as s (s.schluessel)}<span class:jetzt={s.art === "jetzt"}>{s.name}</span>{/each}
    </div>
  {/if}
</div>
