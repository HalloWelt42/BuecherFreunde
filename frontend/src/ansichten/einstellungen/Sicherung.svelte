<script lang="ts">
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { sicherungAdresse } from "../../lib/api/config";
  import { groesse } from "../../lib/format";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { vorgaenge } from "./vorgaenge.svelte";

  $effect(() => void vorgaenge.ladeSicherungen());

  // Die Liste trägt die Ortszeit des Servers
  const wann = (z: string) => new Date(z).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
</script>

<p class="klein">Sichert Datenbank, Einstellungen und Angaben als eine Datei. Die Bücher selbst {anschluesse.inWolke ? "liegen in der Kellerwolke" : "liegen im Speicher der App"} und sind nicht enthalten.</p>
{#if vorgaenge.sicherungen?.length}
  {#each vorgaenge.sicherungen as s (s.filename)}
    <div class="stelle zeile-stand eins-knopf">
      <span><b class="dateiname">{s.filename}</b><br /><span class="leise zahl">{wann(s.created_at)}, {groesse(s.size)}</span></span>
      <Knopf text="Herunterladen" symbol="download" nur klein frei href={sicherungAdresse(s.filename)} download={s.filename} />
    </div>
  {/each}
{:else}
  <p class="leise">{vorgaenge.sicherungen ? "Noch keine Sicherung vorhanden." : "Die Liste der Sicherungen kam nicht an."}</p>
{/if}
<div class="reihe"><Knopf text="Jetzt sichern" symbol="floppy-disk" klein laeuft={vorgaenge.laeuft.sicherung} onclick={() => void vorgaenge.sichere()} /></div>
