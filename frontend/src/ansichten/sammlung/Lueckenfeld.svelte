<script lang="ts">
  // Das Feld zum fehlenden Band (BF-75): Angaben aus den Quellen, Kopieren, Suchen mit der eigenen Suchadresse, Hochladen in
  // die Lücke über die Vorschau, "Gibt es nicht" und "Brauche ich nicht". Ohne Suchadresse gibt es nur Kopieren. Steht der Band
  // im eigenen Katalog der gemeinfreien Bücher (BF-98): "In die Lücke holen" und "Bei Gemeinfreie Bücher zeigen".
  import type { Luecke, Reihe } from "../../lib/api/luecken";
  import { formatName, sprache } from "../../lib/format";
  import { kopiere } from "../../lib/kopieren";
  import { ich } from "../../lib/stand/ich.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { brauchbar } from "../hinzu/dateien";
  import type { Lueckenstand } from "./lueckenstand.svelte";

  let { luecke, reihe, stand, autor, onschliessen }: { luecke: Luecke; reihe: Reihe; stand: Lueckenstand; autor: string; onschliessen: () => void } = $props();
  let feld: HTMLInputElement | undefined = $state();
  let darfHochladen = $derived(ich.darf("hinzufuegen"));
  let darfAusblenden = $derived(ich.darf("bearbeiten"));
  let gemeinfrei = $derived(darfHochladen ? luecke.gemeinfrei : null);

  // Wie beim Hochladen: erst festhalten, dann schließen, dann weiter in die Vorschau oder zu den gemeinfreien Büchern
  function holeGemeinfrei() {
    const l = luecke;
    onschliessen();
    void stand.holeGemeinfrei(l);
  }

  function zeigeGemeinfrei() {
    const l = luecke;
    onschliessen();
    stand.zeigeGemeinfrei(l);
  }

  function gewaehlt() {
    const dateien = brauchbar(feld?.files ?? []);
    // Erst festhalten, dann schließen: danach gibt es das Feld und seine Angaben nicht mehr
    const l = luecke;
    if (feld) feld.value = "";
    onschliessen();
    void stand.hochladen(dateien, l);
  }

  async function blendeAus(grund: "gibt_es_nicht" | "brauche_ich_nicht") {
    if (await stand.ausblenden(luecke, reihe, grund)) onschliessen();
  }
</script>

<div class="feldkopf"><b>Band {luecke.nummer} fehlt</b><span class="schiebt"><Knopf text="Schließen" symbol="xmark" nur klein frei onclick={onschliessen} /></span></div>
<dl class="angaben">
  <dt>Titel</dt><dd>{luecke.titel || "unbekannt"}</dd>
  {#if luecke.autor || autor}<dt>Autor</dt><dd>{luecke.autor || autor}</dd>{/if}
  <dt>Sammlung</dt><dd>{reihe.reihe}</dd>
  <dt>Nummer</dt><dd class="zahl">{luecke.nummer}, {reihe.name}</dd>
  {#if luecke.isbn}<dt>ISBN</dt><dd class="zahl">{luecke.isbn}</dd>{/if}
  {#if luecke.jahr}<dt>Jahr</dt><dd class="zahl">{luecke.jahr}</dd>{/if}
</dl>
{#if gemeinfrei}
  <div class="gemeinfrei-feld">
    <span><Symbol name="landmark" /> <b>Gemeinfrei zu haben</b></span>
    <small>Im eigenen Katalog des Project Gutenberg: {[formatName(gemeinfrei.download_format), ...gemeinfrei.sprachen.map(sprache)].filter(Boolean).join(", ")}</small>
    <div class="feldtasten">
      <Knopf text="In die Lücke holen" symbol="download" haupt titel="Holen und in der Vorschau dieser Lücke bestätigen" onclick={holeGemeinfrei} />
      <Knopf text="Bei Gemeinfreie Bücher zeigen" symbol="arrow-right" onclick={zeigeGemeinfrei} />
    </div>
  </div>
{/if}
<div class="feldtasten">
  <Knopf text="Kopieren" symbol="copy" klasse={luecke.suchadresse ? "" : "voll"} titel="Titel, Autor, Nummer und ISBN kopieren" onclick={() => void kopiere(luecke.kopieren)} />
  {#if luecke.suchadresse}<Knopf text="Suchen" symbol="magnifying-glass" href={luecke.suchadresse} extern titel="Mit deiner Suchadresse suchen" />{/if}
  {#if darfHochladen}<Knopf text="Hochladen" symbol="cloud-arrow-up" haupt klasse="voll" titel="Datei in diese Lücke, über die Vorschau" onclick={() => feld?.click()} />{/if}
</div>
{#if darfAusblenden}
  <div class="feldtrenner"></div>
  <div class="feldtasten">
    <Knopf text="Gibt es nicht" symbol="ban" klein frei gesperrt={stand.arbeitet} titel="Den Platzhalter ausblenden, zurückholen geht unter Bearbeiten" onclick={() => void blendeAus("gibt_es_nicht")} />
    <Knopf text="Brauche ich nicht" symbol="eye-slash" klein frei gesperrt={stand.arbeitet} titel="Den Platzhalter ausblenden, zurückholen geht unter Bearbeiten" onclick={() => void blendeAus("brauche_ich_nicht")} />
  </div>
{/if}
{#if darfHochladen}<input type="file" multiple accept=".pdf,.epub,.mobi,.txt,.md,.zip" hidden bind:this={feld} onchange={gewaehlt} />{/if}
