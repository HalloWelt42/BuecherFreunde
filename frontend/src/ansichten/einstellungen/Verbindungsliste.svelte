<script lang="ts">
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Guete } from "../../lib/typen";

  let prueft = $state("");

  interface Zeile {
    name: string;
    stand: Guete | "aus";
    text: string;
    oeffnen: string;                  // Adresse der Anwendung des Dienstes: statt "Prüfen" ein Knopf "Öffnen"
  }
  // Assistent und Nachschlag sind eigene Anwendungen; ihre Zeile öffnet sie, geprüft werden sie mit allen anderen
  let adressen = $derived<Record<string, string>>({ assistent: verbindungen.assistent, nachschlag: anschluesse.jetzt.nachschlag });
  let zeilen = $derived<Zeile[]>([
    { name: "BücherFreunde", ...verbindungen.app, oeffnen: "" },
    ...verbindungen.liste.map((v) => ({ name: v.name, stand: v.stand, text: v.text, oeffnen: adressen[v.kennung] ?? "" })),
  ]);

  async function pruefe(name: string) {
    prueft = name;
    await verbindungen.pruefen();
    prueft = "";
    const z = zeilen.find((x) => x.name === name);
    if (!z) return;
    const ton = z.stand === "gut" ? "gut" : z.stand === "schlecht" ? "schlecht" : z.stand === "warn" ? "warn" : "info";
    melde[ton](`${name}: ${z.text}`);
  }
</script>

{#each zeilen as z (z.name)}
  <div class="stelle zeile-stand">
    <span class="led {z.stand}"></span>
    <span><b>{z.name}</b><br /><span class="leise">{z.text}</span></span>
    {#if z.oeffnen}
      <Knopf text="Öffnen" symbol="arrow-up-right-from-square" klein extern href={z.oeffnen} />
    {:else}
      <Knopf text="Prüfen" symbol="stethoscope" klein laeuft={prueft === z.name} onclick={() => void pruefe(z.name)} />
    {/if}
  </div>
{/each}
{#if !verbindungen.liste.length}<p class="leise">Nichts weiter angeschlossen.</p>{/if}
