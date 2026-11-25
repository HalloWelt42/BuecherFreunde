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
  }
  let zeilen = $derived<Zeile[]>([
    { name: "BücherFreunde", ...verbindungen.app },
    ...verbindungen.liste.map((v) => ({ name: v.name, stand: v.stand, text: v.text })),
    ...(anschluesse.jetzt.ki ? [{ name: "KI", ...verbindungen.ki }] : []),
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
    <Knopf text="Prüfen" symbol="stethoscope" klein laeuft={prueft === z.name} onclick={() => void pruefe(z.name)} />
  </div>
{/each}
{#if verbindungen.assistent}
  <div class="stelle zeile-stand">
    <span class="led aus"></span>
    <span><b>Assistent</b><br /><span class="leise">Eingerichtet, antwortet auf Fragen zu den Büchern</span></span>
    <Knopf text="Öffnen" symbol="arrow-up-right-from-square" klein extern href={verbindungen.assistent} />
  </div>
{/if}
{#if !verbindungen.liste.length}<p class="leise">Nichts weiter angeschlossen.</p>{/if}
