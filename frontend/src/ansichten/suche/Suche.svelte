<script lang="ts">
  import { anzahl, zahl } from "../../lib/format";
  import { navigate } from "../../lib/router.svelte";
  import { rollstand } from "../../lib/rollstand";
  import { holeBuch } from "../../lib/api/books";
  import { schale } from "../../lib/stand/schale.svelte";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { suche, suchwerte } from "../../lib/stand/suche.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Nachlader from "../../lib/teile/Nachlader.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import Antwort from "./Antwort.svelte";
  import Sinntreffer from "./Sinntreffer.svelte";
  import Suchanfang from "./Suchanfang.svelte";
  import Suchhilfe from "./Suchhilfe.svelte";
  import Worttreffer from "./Worttreffer.svelte";
  import Materialtreffer from "./Materialtreffer.svelte";
  import { Suchlauf } from "./suchlauf.svelte";
  import { filtername, ohneFilter } from "./suchsprache";

  const lauf = new Suchlauf();
  let hilfe = $state(false);
  let frage = $derived(suche.wort.trim());
  let art = $derived(suche.art);
  let filterliste = $derived(Object.entries(lauf.filter));

  $effect(() => {
    if (frage) void lauf.starte(frage, art);
  });

  // Der erste Treffer steht gleich in der Vorschau, wenn dort noch nichts ist
  $effect(() => {
    const erster = lauf.funde[0];
    if (!erster || wahl.buch || !schale.mitVorschau) return;
    holeBuch(erster.art === "wort" ? erster.wort.book_id : erster.art === "sinn" ? erster.sinn.buch_id : erster.material.buch_id).then((b) => wahl.falls(b)).catch(() => {});
  });

  function nimmFilterWeg(name: string) {
    const rest = ohneFilter(frage, name);
    navigate(rest ? suche.adresse(rest) : "/search");
  }

  let gezeigt = $derived(lauf.funde.length);
  let zahltext = $derived(!lauf.fertig && !gezeigt ? "" : lauf.zahl > gezeigt ? `${zahl(gezeigt)} von ${zahl(lauf.zahl)} Treffern` : anzahl(gezeigt, "Treffer", "Treffer"));
</script>

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  <h1>{frage || "Suche"}</h1>
  <span class="leise zahl" role="status">{frage ? zahltext : ""}</span>
  {#if anschluesse.jetzt.bedeutung}<span class="nur-schmal schiebt"><Segment name="Suchart" werte={suchwerte} wert={art} onwahl={(w) => suche.waehleArt(w)} /></span>{/if}
</div>

<div class="inhalt rollen" style:gap=".5rem" use:rollstand={`/search?${frage}&${art}`}>
  <div class="reihe">
    {#each filterliste as [name, wert] (name)}<Chip text="{filtername(name)}: {wert}" titel="Filter herausnehmen" symbol="xmark" onclick={() => nimmFilterWeg(name)} />{/each}
    <Knopf text="Suchsprache" symbol="circle-question" klein frei aufgeklappt={hilfe} onclick={() => (hilfe = !hilfe)} />
  </div>
  {#if hilfe}<Suchhilfe />{/if}

  {#if !frage}
    <Suchanfang />
  {:else}
    {#if lauf.grund && art !== "woerter"}<p class="marke-text warn" role="status">Bedeutung: {lauf.grund}{art === "beides" ? ". Die Wörter gelten trotzdem." : "."}</p>{/if}
    {#if lauf.fehler}<Zustand art="fehler" text={lauf.fehler} onerneut={() => void lauf.starte(frage, art)} />{/if}
    {#if lauf.laedt && !gezeigt}<Zustand art="laedt" text="Wird gesucht" />{/if}
    {#each lauf.funde as fund (fund.schluessel)}
      {#if fund.art === "wort"}<Worttreffer treffer={fund.wort} {frage} />{:else if fund.art === "material"}<Materialtreffer treffer={fund.material} {frage} />{:else}<Sinntreffer treffer={fund.sinn} />{/if}
    {/each}
    {#if lauf.fertig && !gezeigt && !lauf.fehler}
      <Zustand text={art === "bedeutung" && lauf.grund ? "Nach Bedeutung geht es gerade nicht." : "Nichts gefunden."}>
        {#if art === "bedeutung"}<Knopf text="Nach Wörtern suchen" symbol="font" klein onclick={() => suche.waehleArt("woerter")} />{/if}
      </Zustand>
    {/if}
    {#if lauf.fertig && gezeigt}<Antwort {frage} />{/if}
    {#if lauf.gesamt > lauf.woerter.length}<Nachlader geladen={lauf.woerter.length} gesamt={lauf.gesamt} laedt={lauf.laedt} onmehr={() => void lauf.mehr(frage)} />{/if}
  {/if}
</div>
