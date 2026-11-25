<script lang="ts">
  // Wo die Daten liegen: neue Orte mit Platz, sonst die Verzeichnisse des Servers
  import { ladePfade, type Verzeichnisse } from "../../lib/api/config";
  import { ladeOrte } from "../../lib/api/orte";
  import { groesse } from "../../lib/format";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Ort } from "../../lib/typen";

  const erklaerung: [keyof Verzeichnisse, string, string][] = [
    ["datenbank", "Datenbank", "Angaben, Notizen, Lesestände und Suchindex"],
    ["speicher", "Bestand", "Originale, Umschläge und Volltexte, nach Prüfsumme abgelegt"],
    ["import", "Eingangsordner", "Neue Dateien hier ablegen, das Einlesen findet sie"],
    ["extern", "Alte Sammlung", "Nur lesend, zum Einlesen und zum Erkennen von Doppeln"],
  ];

  let orte = $state<Ort[] | null>(null);
  let verzeichnisse = $state<Verzeichnisse | null>(null);
  let fertig = $state(false);

  async function hole() {
    fertig = false;
    const [o, p] = await Promise.allSettled([ladeOrte(), ladePfade()]);
    orte = o.status === "fulfilled" ? o.value : null;
    verzeichnisse = p.status === "fulfilled" ? p.value : null;
    fertig = true;
  }

  $effect(() => void hole());

  function platz(ort: Ort): string {
    const teile = [ort.belegt === null ? "" : `${groesse(ort.belegt)} belegt`, ort.frei === null ? "" : `${groesse(ort.frei)} frei`];
    return teile.filter(Boolean).join(", ");
  }
</script>

<p class="leise">Nur Anzeige. Die Orte kommen beim Start aus der Einrichtung.</p>
{#if !fertig}
  <Zustand art="laedt" text="Orte werden geholt" />
{:else if orte?.length}
  {#each orte as ort (ort.kennung)}
    <div class="stelle zeile-stand zwei">
      <span class="led {ort.stand}"></span>
      <span><b>{ort.name}</b>{#if platz(ort)}{" "}<span class="leise zahl">{platz(ort)}</span>{/if}<br /><code class="pfad">{ort.pfad}</code></span>
    </div>
  {/each}
{:else if verzeichnisse}
  {#each erklaerung as [schluessel, name, wozu] (schluessel)}
    {#if verzeichnisse[schluessel]}
      <div class="stelle zeile-stand eins">
        <span><b>{name}</b><br /><code class="pfad">{verzeichnisse[schluessel]}</code><br /><span class="leise">{wozu}</span></span>
      </div>
    {/if}
  {/each}
{:else}
  <Zustand art="fehler" text="Noch keine Angaben vom Server." onerneut={() => void hole()} />
{/if}
