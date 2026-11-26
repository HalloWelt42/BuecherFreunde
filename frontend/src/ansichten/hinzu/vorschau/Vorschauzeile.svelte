<script lang="ts">
  // Eine Datei der Vorschau (BF-80): Art, Kategorie, Sammlung und Band, Sprache, Doppel und Material, je mit Herkunft. Am
  // Rechner eine Zeile der Tabelle, schmal eine Karte mit den Werten als Chips.
  import { aenderbar, artAnzeige, doppelwerte, laeuftNoch, wartet, zusatz } from "../../../lib/annahme/vorschau";
  import type { Doppelwahl, Vorschauzeile } from "../../../lib/annahme/vorschautypen";
  import { groesse, sprache as sprachname } from "../../../lib/format";
  import { findeKategorie, farbeVon } from "../../../lib/katalog";
  import { arten } from "../../../lib/stand/arten.svelte";
  import { bestand } from "../../../lib/stand/bestand.svelte";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Flagge from "../../../lib/teile/Flagge.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Umschlag from "../../../lib/teile/Umschlag.svelte";
  import Herkunft from "./Herkunft.svelte";
  import Vorschaubild from "./Vorschaubild.svelte";
  import Wert from "./Wert.svelte";
  import type { Vorschaustand } from "./vorschaustand.svelte";

  let { zeile, stand, onaendern }: { zeile: Vorschauzeile; stand: Vorschaustand; onaendern: (z: Vorschauzeile) => void } = $props();

  let f = $derived(zeile.felder);
  let waehlbar = $derived(stand.offen && aenderbar(zeile) && !!f);
  let gewaehlt = $derived(stand.gewaehlt.includes(zeile.id));
  let istMaterial = $derived(zeile.rolle === "material");
  let zielzeile = $derived(f?.ziel?.aufnahme ? (stand.zeilen.find((z) => z.id === f?.ziel?.aufnahme) ?? null) : null);
  let art = $derived(artAnzeige(f?.art.wert ?? "", (id) => arten.typName(id)));
  let artKlein = $derived(istMaterial ? zusatz(zeile.name, zielzeile?.name ?? f?.ziel?.titel ?? "") || (zeile.name.split(".").pop() ?? "").toUpperCase() : art.klein);
  let kategorien = $derived((f?.kategorien.wert ?? []).map((id) => findeKategorie(bestand.katalog, id)).filter((k) => !!k));
  let sammlung = $derived(f?.sammlung.wert ? bestand.sammlung(f.sammlung.wert) : undefined);
  let etiketten = $derived(f?.etiketten.wert ?? []);
  let doppel = $derived(f?.doppel);
  let mitWahl = $derived(!!doppel && (doppel.art !== "neu" || doppel.wahl !== "neu"));
  let ort = $derived([zeile.ordner, groesse(zeile.groesse)].filter(Boolean).join(", "));
  let kiPrueft = $derived(zeile.ki === "offen" && !kategorien.length);

  const doppelSetzen = (w: string) => void stand.aendere([zeile.id], { doppel: w as Doppelwahl });
</script>

<div class="vzeile" class:gewaehlt class:weglassen={zeile.rolle === "doppel"}>
  <label class="haekchen wahl"><input type="checkbox" checked={gewaehlt} disabled={!waehlbar} aria-label="{zeile.name} anhaken" onchange={(e) => stand.waehle(zeile.id, e.currentTarget.checked)} /></label>
  <span class="bild"><Vorschaubild {zeile} /></span>
  <span class="vdatei"><b title={[zeile.ordner, zeile.name].filter(Boolean).join("/")}>{zeile.name}</b><small>{#if zeile.ordner}<Symbol name="folder" /> {/if}{ort}</small></span>
  <span class="felder">
    {#if !f}
      {#if laeuftNoch(zeile)}
        <span class="vlaeuft marke-text info"><Symbol name="circle-notch" dreht />{zeile.text || "Wird gelesen"}</span>
      {:else}
        <span class="vlaeuft marke-text info"><Symbol name={zeile.rolle === "doppel" ? "clone" : "circle-info"} />{zeile.text}</span>
      {/if}
    {:else}
      <Wert text={art.text} klein={artKlein} herkunft={f.art.herkunft}>{#snippet vorn()}<Symbol name={art.symbol} />{/snippet}</Wert>
      {#if istMaterial && f.ziel}
        <Wert zu text="zu {f.ziel.titel}" klein={f.ziel.aufnahme ? (stand.vorschau?.name.toLowerCase().endsWith(".zip") ? "aus der ZIP" : "aus dieser Vorschau") : "im Bestand"} herkunft={f.art.herkunft}>
          {#snippet vorn()}{#if zielzeile}<span class="umschlag"><Vorschaubild zeile={zielzeile} /></span>{:else if f?.ziel?.buch_id}<Umschlag buch={{ id: f.ziel.buch_id, title: f.ziel.titel }} />{/if}{/snippet}
        </Wert>
      {:else}
        {#if kiPrueft}
          <span class="vwert"><span class="marke-text info"><Symbol name="circle-notch" dreht />KI prüft</span></span>
        {:else if kategorien.length}
          {@const k = kategorien[0]!}
          <Wert text="{k.kategorie.name}{kategorien.length > 1 ? ` +${kategorien.length - 1}` : ''}" titel={kategorien.map((x) => x?.kategorie.name).join(", ")} herkunft={f.kategorien.herkunft}>
            {#snippet vorn()}<Katalogzeichen name={k.kategorie.zeichen} farbe={farbeVon(k.kategorie, k.bereich)} groesse="klein" />{/snippet}
            {#snippet unter()}{#if etiketten.length}<Symbol name="tag" /> {etiketten.join(", ")}<Herkunft herkunft={f?.etiketten.herkunft ?? null} />{/if}{/snippet}
          </Wert>
        {:else if etiketten.length}
          <Wert text={etiketten.join(", ")} herkunft={f.etiketten.herkunft}>{#snippet vorn()}<Symbol name="tag" />{/snippet}</Wert>
        {:else}
          <span class="vohne"></span>
        {/if}
        {#if sammlung}
          <Wert text={sammlung.name} klein={f.band.wert ? `Band ${f.band.wert}` : ""} herkunft={f.sammlung.herkunft}>{#snippet vorn()}<span class="farbe" style:background={sammlung?.color || "var(--tinte-3)"}></span>{/snippet}</Wert>
        {:else}
          <span class="vohne"></span>
        {/if}
        {#if f.sprache.wert}
          <Wert text={sprachname(f.sprache.wert)} herkunft={f.sprache.herkunft}>{#snippet vorn()}<Flagge sprache={f?.sprache.wert ?? ""} groesse="1rem" />{/snippet}</Wert>
        {:else}
          <span class="vohne"></span>
        {/if}
      {/if}
      {#if doppel && mitWahl}
        <span class="vdoppel">
          <Auswahl name="Doppel" klein werte={doppelwerte(doppel)} wert={doppel.wahl} gesperrt={!waehlbar || doppel.art === "gleich" || stand.arbeitet} onwahl={doppelSetzen} />
          {#if doppel.grund}<small title={doppel.grund}>{doppel.grund}</small>{/if}
        </span>
      {:else}
        <span class="vdoppel"><span class="marke-text gut"><Symbol name="plus" />Neu</span></span>
      {/if}
      {#if zeile.material}
        <span class="vwert" title="{zeile.material} {zeile.material === 1 ? 'Datei' : 'Dateien'} als Begleitmaterial"><Symbol name="paperclip" /><span class="text"><span>+{zeile.material}</span></span></span>
      {:else}
        <span class="vohne"></span>
      {/if}
      {#each f.hinweise as hinweis (hinweis)}<span class="vwarnung marke-text warn"><Symbol name="triangle-exclamation" />{hinweis}</span>{/each}
      {#if !stand.offen && !wartet(zeile) && zeile.text}<span class="vwarnung leise">{zeile.text}</span>{/if}
    {/if}
  </span>
  <span class="tun"><Knopf text="Ändern" titel="{zeile.name} zuordnen" symbol="pen" nur klein frei gesperrt={!waehlbar} onclick={() => onaendern(zeile)} /></span>
</div>
