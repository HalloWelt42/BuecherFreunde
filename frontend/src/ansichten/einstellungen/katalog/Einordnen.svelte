<script lang="ts">
  // Einordnen in Stapeln (BF-69): Lauf mit Stand und Pause, darunter die Vorschläge einer Kategorie. Lauf, Wahl der Kategorie
  // und Tasten bleiben stehen, nur die Liste rollt.
  import { anzahl, zahl } from "../../../lib/format";
  import { findeKategorie } from "../../../lib/katalog";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Nachlader from "../../../lib/teile/Nachlader.svelte";
  import { einordnen, laufanteil, laufkopf, laufzahlen, stapeltext } from "./einordnung.svelte";
  import Vorschlagszeile from "./Vorschlagszeile.svelte";

  $effect(() => void einordnen.laden());

  let stand = $derived(einordnen.stand);
  let zeigeLauf = $derived(!!stand && (einordnen.belegt || stand.stapel_gesamt > 0));
  let gewaehlt = $derived(einordnen.kategorie === null ? null : findeKategorie(bestand.katalog, einordnen.kategorie));
  let offen = $derived(einordnen.uebersicht.find((u) => u.kategorie_id === einordnen.kategorie)?.anzahl ?? einordnen.gesamt);
  let angehakt = $derived(einordnen.gewaehlt);
  let besetzt = $derived(einordnen.arbeitet.size > 0);

  /** Kategorien mit offenen Vorschlägen, nach Bereichen in der Reihenfolge des Katalogs */
  let wahl = $derived.by(() => {
    const offene = new Map(einordnen.uebersicht.map((u) => [u.kategorie_id, u.anzahl]));
    return (bestand.katalog?.bereiche ?? [])
      .map((b): [string, [string, string][]] => [b.name, b.kategorien.flatMap((k): [string, string][] => (k.id !== undefined && offene.has(k.id) ? [[String(k.id), `${k.name} (${zahl(offene.get(k.id))})`]] : []))])
      .filter(([, liste]) => liste.length);
  });
</script>

<Karte titel="Einordnen" symbol="wand-magic-sparkles" breit id="einordnen">
  {#snippet neben()}{#if !einordnen.belegt}<Knopf text="Einordnen" symbol="play" klein onclick={() => void einordnen.starte()} />{/if}{/snippet}
  {#if stand && zeigeLauf}
    <div class="einordnenlauf platte">
      <div class="reihe">
        <b>{laufkopf(stand)}</b><span class="leise zahl">{stapeltext(stand)}</span>
        {#if einordnen.belegt}
          <span class="schiebt">
            {#if stand.pause}<Knopf text="Fortsetzen" symbol="play" klein onclick={() => void einordnen.fortsetzen()} />
            {:else}<Knopf text="Pause" symbol="pause" klein onclick={() => void einordnen.pause()} />{/if}
          </span>
        {/if}
      </div>
      {#if laufanteil(stand) !== null}<Balken anteil={laufanteil(stand) ?? 0} name="Stand des Einordnens" />{/if}
      <span class="leise zahl">{laufzahlen(stand)}</span>
      {#if stand.grund}<span class="marke-text warn">{stand.grund}</span>{/if}
    </div>
  {/if}

  {#if wahl.length && gewaehlt}
    {#if wahl.length > 1 || wahl[0][1].length > 1}<div class="feld kategoriewahl">Kategorie<Auswahl name="Kategorie mit Vorschlägen" gruppen={wahl} wert={String(einordnen.kategorie)} onwahl={(w) => void einordnen.waehle(Number(w))} /></div>{/if}
    <div class="kategoriekopf">
      <Katalogzeichen name={gewaehlt.kategorie.zeichen} farbe={gewaehlt.kategorie.farbe || gewaehlt.bereich.farbe} groesse="gross" />
      <b>{gewaehlt.kategorie.name}</b><span class="leise">in {gewaehlt.bereich.name}</span><span class="leise zahl">{anzahl(offen, "Vorschlag", "Vorschläge")}</span>
      <span class="schiebt reihe tasten">
        <Knopf text="Alle {zahl(offen)} annehmen" symbol="check-double" haupt klein gesperrt={besetzt || !offen} onclick={() => void einordnen.annehmenAlle()} />
        <Knopf text="{zahl(angehakt.length)} angehakte annehmen" symbol="check" klein gesperrt={besetzt || !angehakt.length} onclick={() => void einordnen.annehmen(angehakt)} />
        <Knopf text="Angehakte ablehnen" symbol="xmark" klein frei gesperrt={besetzt || !angehakt.length} onclick={() => void einordnen.ablehnen(angehakt)} />
      </span>
    </div>
    <div class="verwaltung vorschlagsliste rollen">
      {#each einordnen.vorschlaege as v (v.id)}<Vorschlagszeile vorschlag={v} />{/each}
      {#if einordnen.gesamt > einordnen.vorschlaege.length}<Nachlader geladen={einordnen.vorschlaege.length} gesamt={einordnen.gesamt} laedt={einordnen.laedt} onmehr={() => void einordnen.mehr()} />{/if}
    </div>
  {:else if einordnen.geladen && !einordnen.belegt}
    <p class="leise">Keine offenen Vorschläge.</p>
  {/if}
</Karte>
