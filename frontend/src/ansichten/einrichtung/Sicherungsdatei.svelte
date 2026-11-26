<script lang="ts">
  // Eine Sicherung als Datei hochladen, in Teilen: nach einer Unterbrechung geht es am Stand des Servers weiter. Danach lässt
  // sie sich wählen wie eine aus dem Sicherungsordner.
  import { onDestroy } from "svelte";
  import { ladeHochladestand, meldeHochladenAn, sendeSicherungsteil, type Hochladestand } from "../../lib/api/einrichtung";
  import { hochladenZaehlen } from "../../lib/api/client";
  import { pruefsumme } from "../../lib/annahme/pruefsumme";
  import { ladeSicherungHoch, type Ladestand, type Sicherungsdienst } from "../../lib/einrichtung/sicherungslader";
  import { groesse } from "../../lib/format";
  import Balken from "../../lib/teile/Balken.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { onfertig }: { onfertig: (h: Hochladestand) => void } = $props();

  const dienst: Sicherungsdienst = { anmelden: meldeHochladenAn, teil: sendeSicherungsteil, stand: ladeHochladestand };

  let feld: HTMLInputElement | undefined = $state();
  let datei = $state<File | null>(null);
  let stand = $state<Ladestand | null>(null);
  let fehler = $state("");
  let ueber = $state(false);
  let abbruch: AbortController | null = null;

  async function lade(neu: File) {
    abbruch?.abort();
    const a = (abbruch = new AbortController());
    datei = neu;
    fehler = "";
    hochladenZaehlen(1);
    try {
      onfertig(await ladeSicherungHoch(neu, dienst, pruefsumme, (s) => (stand = s), a.signal));
    } catch (e) {
      if (!a.signal.aborted) fehler = e instanceof Error ? e.message : String(e);
      stand = null;
    } finally {
      hochladenZaehlen(-1);
    }
  }

  function gewaehlt() {
    const neu = feld?.files?.[0];
    if (feld) feld.value = "";
    if (neu) void lade(neu);
  }

  function abgelegt(e: DragEvent) {
    e.preventDefault();
    ueber = false;
    const neu = e.dataTransfer?.files?.[0];
    if (neu) void lade(neu);
  }

  onDestroy(() => abbruch?.abort());
</script>

<section class="ablage" class:ueber role="group" aria-label="Sicherung hochladen" ondragover={(e) => { e.preventDefault(); ueber = true; }} ondragleave={() => (ueber = false)} ondrop={abgelegt}>
  <Symbol name="file-arrow-up" />
  <div>
    <b>Sicherung hierher ziehen</b>
    <p class="leise">Eine ZIP aus einem Sicherungsordner, in Teilen hochgeladen; nach einer Unterbrechung geht es am Stand weiter.</p>
  </div>
  <Knopf text="Datei wählen" symbol="plus" haupt gesperrt={stand?.lage === "laedt" || stand?.lage === "prueft"} onclick={() => feld?.click()} />
  <input type="file" accept=".zip,application/zip" hidden bind:this={feld} onchange={gewaehlt} />
</section>
{#if datei && (stand || fehler)}
  <div class="platte ew-auftrag">
    <div class="reihe"><b class="dateiname">{datei.name}</b><span class="schiebt leise zahl">{groesse(datei.size)}</span></div>
    {#if stand}
      <Balken anteil={stand.anteil} name="Sicherung hochladen" gut={stand.lage === "fertig"} />
      <span class="leise">{stand.text}</span>
    {/if}
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  </div>
{/if}

<style>
  .ueber {
    background: var(--messing-hauch);
    outline-color: var(--messing);
  }
</style>
