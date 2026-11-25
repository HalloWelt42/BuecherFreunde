<script lang="ts">
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { schale } from "../stand/schale.svelte";
  import { suche, suchwerte } from "../stand/suche.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Segment from "../teile/Segment.svelte";
  import Logo from "./Logo.svelte";
  import Suchfeld from "./Suchfeld.svelte";

  let laufend = $derived(annahme.laufend.length + auftraege.laufend);
</script>

<header class="kopf glas klar">
  <Knopf text="Seitenleiste ein- und ausblenden" symbol="bars" nur frei klasse="leisteknopf" onclick={() => schale.leisteUmschalten()} />
  <a class="zeichen" href="/" aria-label="Zur Bibliothek"><Logo /><span>BücherFreunde</span></a>
  <Suchfeld id="suchfeld">
    <span class="nur-weit"><Segment name="Suchart" werte={suchwerte} wert={suche.art} onwahl={(w) => suche.waehleArt(w)} /></span>
  </Suchfeld>
  <span class="nicht-telefon"><Knopf text="Hinzufügen" symbol="plus" haupt href="/import" /></span>
  <Knopf text={laufend ? `${laufend} ${laufend === 1 ? "läuft" : "laufen"}` : "Aufträge"} symbol="arrows-rotate" klasse="auftragsknopf" aufgeklappt={schale.offen === "auftraege"} onclick={() => schale.umschalten("auftraege")} />
  <span class="nur-breit reihe">
    <Knopf text="Schnellnotiz" symbol="note-sticky" nur frei gedrueckt={schale.notizOffen} onclick={() => (schale.notizOffen = !schale.notizOffen)} />
    <Knopf text="Danke sagen" symbol="heart" nur frei href="/danke" />
  </span>
  <Knopf text="Darstellung: Glas, Schrift, hell und dunkel" symbol="circle-half-stroke" nur frei aufgeklappt={schale.offen === "darstellung"} onclick={() => schale.umschalten("darstellung")} />
  <span class="nur-breit"><Knopf text="Konto und Abmelden" symbol="user" nur frei aufgeklappt={schale.offen === "konto"} onclick={() => schale.umschalten("konto")} /></span>
</header>
