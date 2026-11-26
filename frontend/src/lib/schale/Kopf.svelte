<script lang="ts">
  import { anzahl } from "../format";
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { schale } from "../stand/schale.svelte";
  import { anschluesse } from "../stand/anschluesse.svelte";
  import { suche, suchwerte } from "../stand/suche.svelte";
  import { ich } from "../stand/ich.svelte";
  import { mitAuftraegen } from "../stand/abrufe";
  import Knopf from "../teile/Knopf.svelte";
  import Profilbild from "../teile/Profilbild.svelte";
  import Segment from "../teile/Segment.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Logo from "./Logo.svelte";
  import Suchfeld from "./Suchfeld.svelte";

  // Der Knopf nennt, was läuft und was auf die Bestätigung wartet (BF-80); in schmalen Fenstern nur Zeichen und Zahl
  let laufend = $derived(annahme.vonSelbst + auftraege.laufend);
  let warten = $derived(annahme.vorschauen.length);
  let teile = $derived([
    laufend ? `${laufend} ${laufend === 1 ? "läuft" : "laufen"}` : annahme.angehalten ? `${annahme.angehalten} pausiert` : "",
    warten ? `${warten} zum Bestätigen` : "",
  ].filter(Boolean));
  let auftragstext = $derived(teile.join(", ") || "Aufträge");
  let kurzzahl = $derived((laufend || annahme.angehalten) + warten);
</script>

<header class="kopf glas klar">
  <Knopf text="Seitenleiste ein- und ausblenden" symbol="bars" nur frei klasse="leisteknopf" onclick={() => schale.leisteUmschalten()} />
  <a class="zeichen" href="/" aria-label="Zur Bibliothek"><Logo /><span>BücherFreunde</span></a>
  <Suchfeld id="suchfeld">
    {#if anschluesse.jetzt.bedeutung}<span class="nur-weit"><Segment name="Suchart" werte={suchwerte} wert={suche.art} onwahl={(w) => suche.waehleArt(w)} /></span>{/if}
  </Suchfeld>
  {#if ich.darf("hinzufuegen")}<span class="nicht-telefon"><Knopf text="Hinzufügen" symbol="plus" haupt href="/import" /></span>{/if}
  {#if mitAuftraegen() || auftraege.alleEigenen.length}
    <button type="button" class="knopf auftragsknopf" title={auftragstext} aria-label={auftragstext} aria-expanded={schale.offen === "auftraege"} onclick={() => schale.umschalten("auftraege")}>
      <Symbol name="arrows-rotate" /><span class="lang">{auftragstext}</span>{#if kurzzahl}<span class="kurz zahl">{kurzzahl}</span>{/if}
    </button>
  {/if}
  <span class="nur-breit reihe">
    <Knopf text="Schnellnotiz" titel={notizblock.woerter ? `Schnellnotiz, ${anzahl(notizblock.woerter, "Wort", "Wörter")}` : "Schnellnotiz"} symbol="note-sticky" nur frei gedrueckt={schale.notizOffen} onclick={() => (schale.notizOffen = !schale.notizOffen)} />
    <Knopf text="Danke sagen" symbol="heart" nur frei href="/danke" />
  </span>
  <Knopf text="Darstellung: Glas, Schrift, hell und dunkel" symbol="circle-half-stroke" nur frei aufgeklappt={schale.offen === "darstellung"} onclick={() => schale.umschalten("darstellung")} />
  <!-- Wer gerade liest (BF-78): sein Bild öffnet Profil, Wechsel und das Konto des Geräts -->
  <button type="button" class="knopf nur frei" aria-label="Profil {ich.profil?.name ?? ''}, wechseln und Konto" title={ich.profil?.name} aria-expanded={schale.offen === "konto"} onclick={() => schale.umschalten("konto")}><Profilbild profil={ich.profil} groesse="1.875rem" /></button>
</header>
