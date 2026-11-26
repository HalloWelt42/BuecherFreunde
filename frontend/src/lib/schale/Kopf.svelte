<script lang="ts">
  import { anzahl } from "../format";
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { schale } from "../stand/schale.svelte";
  import { anschluesse } from "../stand/anschluesse.svelte";
  import { suche, suchwerte } from "../stand/suche.svelte";
  import { ich } from "../stand/ich.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Profilbild from "../teile/Profilbild.svelte";
  import Segment from "../teile/Segment.svelte";
  import Logo from "./Logo.svelte";
  import Suchfeld from "./Suchfeld.svelte";

  let laufend = $derived(annahme.vonSelbst + auftraege.laufend);
  let auftragstext = $derived(laufend ? `${laufend} ${laufend === 1 ? "läuft" : "laufen"}` : annahme.angehalten ? `${annahme.angehalten} angehalten` : "Aufträge");
</script>

<header class="kopf glas klar">
  <Knopf text="Seitenleiste ein- und ausblenden" symbol="bars" nur frei klasse="leisteknopf" onclick={() => schale.leisteUmschalten()} />
  <a class="zeichen" href="/" aria-label="Zur Bibliothek"><Logo /><span>BücherFreunde</span></a>
  <Suchfeld id="suchfeld">
    {#if anschluesse.jetzt.bedeutung}<span class="nur-weit"><Segment name="Suchart" werte={suchwerte} wert={suche.art} onwahl={(w) => suche.waehleArt(w)} /></span>{/if}
  </Suchfeld>
  {#if ich.darf("hinzufuegen")}<span class="nicht-telefon"><Knopf text="Hinzufügen" symbol="plus" haupt href="/import" /></span>{/if}
  <Knopf text={auftragstext} symbol="arrows-rotate" klasse="auftragsknopf" aufgeklappt={schale.offen === "auftraege"} onclick={() => schale.umschalten("auftraege")} />
  <span class="nur-breit reihe">
    <Knopf text="Schnellnotiz" titel={notizblock.woerter ? `Schnellnotiz, ${anzahl(notizblock.woerter, "Wort", "Wörter")}` : "Schnellnotiz"} symbol="note-sticky" nur frei gedrueckt={schale.notizOffen} onclick={() => (schale.notizOffen = !schale.notizOffen)} />
    <Knopf text="Danke sagen" symbol="heart" nur frei href="/danke" />
  </span>
  <Knopf text="Darstellung: Glas, Schrift, hell und dunkel" symbol="circle-half-stroke" nur frei aufgeklappt={schale.offen === "darstellung"} onclick={() => schale.umschalten("darstellung")} />
  <!-- Wer gerade liest (BF-78): sein Bild öffnet Profil, Wechsel und das Konto des Geräts -->
  <button type="button" class="knopf nur frei" aria-label="Profil {ich.profil?.name ?? ''}, wechseln und Konto" title={ich.profil?.name} aria-expanded={schale.offen === "konto"} onclick={() => schale.umschalten("konto")}><Profilbild profil={ich.profil} groesse="1.875rem" /></button>
</header>
