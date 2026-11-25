<script lang="ts">
  import { ladeAblage } from "../../lib/api/orte";
  import { ablageText } from "../../lib/ablage";
  import { anzahl, groesse } from "../../lib/format";
  import { verbindungen } from "../../lib/stand/verbindungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { Ablage, BuchEinzeln } from "../../lib/typen";

  let { buch }: { buch: BuchEinzeln } = $props();
  let ablage = $state<Ablage | null>(null);
  let fehler = $state("");

  $effect(() => {
    let gilt = true;
    fehler = "";
    ladeAblage(buch.id)
      .then((a) => gilt && (ablage = a))
      .catch((e) => gilt && (fehler = e instanceof Error ? e.message : String(e)));
    return () => (gilt = false);
  });

  let volltext = $derived(!ablage?.volltext?.zeichen ? "kein Text gefunden, nicht wörtlich zu finden" : `${ablage.volltext.seiten ? `${anzahl(ablage.volltext.seiten, "Seite", "Seiten")}, ` : ""}wörtlich zu finden`);
</script>

<Karte titel="Wo dieses Buch überall ist" symbol="route" breit>
  <div class="fluss">
    <div class="mulde"><b><Symbol name="cloud" /> Datei</b>{#if ablage?.wolke}<span class="dateiort">{ablageText(ablage.wolke)}</span>, {groesse(ablage.wolke.groesse)}<br /><span class="leise" title={ablage.wolke.sha256}>Prüfsumme {ablage.wolke.sha256.slice(0, 12)}</span>{:else}{fehler || "wird geholt"}{/if}</div>
    <div class="mulde"><b><Symbol name="font" /> Volltext</b>{ablage ? volltext : fehler || "wird geholt"}</div>
    <div class="mulde"><b><Symbol name="brain" /> Bedeutung</b>{ablage ? (ablage.wissen?.text ?? "noch nicht erfasst") : fehler || "wird geholt"}</div>
    {#if verbindungen.assistent}<div class="mulde"><b><Symbol name="comments" /> Assistent</b><a href={verbindungen.frageAdresse(buch.title)} target="_blank" rel="noopener">findet Stellen und springt an die Seite</a></div>{/if}
  </div>
</Karte>

<style>
  .dateiort {
    overflow-wrap: anywhere;
  }
</style>
