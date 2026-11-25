<script lang="ts">
  import type { Annahmezeile, Handlung } from "../../lib/annahme/zeilen";
  import { annahme } from "../../lib/stand/annahme.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Stationen from "../../lib/teile/Stationen.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { zeile, onwaehlen }: { zeile: Annahmezeile; onwaehlen: () => void } = $props();

  const beschriftung: Record<Handlung, [string, string]> = {
    anhalten: ["Anhalten", "pause"], weiter: ["Weiter", "play"], jetzt: ["Jetzt weiter", "play"], waehlen: ["Datei wählen", "folder-open"], erneut: ["Erneut", "rotate-right"], buch: ["Buch öffnen", "book-open"], entfernen: ["Entfernen", "xmark"],
  };
  let erste = $derived(zeile.handlungen[0]);
  let mitEntfernen = $derived(zeile.handlungen.length > 1 && zeile.handlungen.includes("entfernen"));

  async function entferne() {
    // Nur ein halb hochgeladener Eintrag verliert etwas
    if (zeile.gruppe === "laeuft" && zeile.prozent > 0) {
      const ja = await frage({ titel: "Aufnahme abbrechen?", text: zeile.name, folgen: ["Was schon hochgeladen ist, wird verworfen.", "Die Datei auf diesem Gerät bleibt, wie sie ist."], ja: "Abbrechen und entfernen" });
      if (!ja) return;
    }
    await annahme.entferne(zeile);
  }

  async function tun(h: Handlung) {
    try {
      if (h === "waehlen") onwaehlen();
      else if (h === "entfernen") await entferne();
      else if (h === "erneut" && zeile.id !== null) await annahme.erneut(zeile.id);
      else if (zeile.hochladung && h === "anhalten") annahme.anhalten(zeile.hochladung);
      else if (zeile.hochladung) annahme.weiter(zeile.hochladung);
    } catch (e) {
      melde.schlecht(e);
    }
  }
</script>

<div class="aufnahme zeile-aufnahme">
  <Symbol name={zeile.symbol} klasse="marke-text {zeile.ton}" dreht={zeile.symbol === "circle-notch"} />
  <div class="name"><b>{zeile.name}</b> <span class="leise zahl">{zeile.groesse}</span><br /><span class="marke-text {zeile.ton}">{zeile.wort}:</span> <span class="klein">{zeile.text}</span></div>
  <div class="stationen"><Stationen stationen={zeile.stationen} prozent={zeile.prozent} /></div>
  <span class="handlungen">
    {#if erste}<Knopf text={beschriftung[erste][0]} symbol={beschriftung[erste][1]} klein klasse="voll" href={erste === "buch" ? `/book/${zeile.buch}` : undefined} onclick={erste === "buch" ? undefined : () => void tun(erste)} />{/if}
    {#if mitEntfernen}<Knopf text="Entfernen" symbol="xmark" nur klein frei onclick={() => void tun("entfernen")} />{/if}
  </span>
</div>

<style>
  .zeile-aufnahme {
    border-top: 1px solid var(--linie);
  }
  .name {
    min-width: 0;
  }
  .handlungen {
    display: flex;
    gap: 0.25rem;
  }
  .handlungen :global(.voll) {
    flex: 1;
  }
</style>
