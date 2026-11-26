<script lang="ts">
  // Begleitmaterial auf der Buchseite (BF-81): Funde aus dem Abgleich mit Ja oder Nein, die Liste, Hinzufügen von einer
  // oder mehreren Dateien, auch einer ZIP. Kinder lesen das Material freigegebener Bücher nur (BF-78): ändern darf, wer
  // bearbeiten darf, hinzufügen braucht dazu die Annahme, entfernen das Löschen.
  import { anzahl, groesse } from "../../lib/format";
  import { ich } from "../../lib/stand/ich.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import { Materialstand } from "./material.svelte";
  import Materialzeile from "./Materialzeile.svelte";

  let { buch }: { buch: BuchEinzeln } = $props();

  let stand = $derived(new Materialstand(buch.id));
  let feld: HTMLInputElement | undefined = $state();

  let darfHinzu = $derived(ich.darf("bearbeiten") && ich.darf("hinzufuegen"));
  let darfUmbenennen = $derived(ich.darf("bearbeiten"));
  let darfEntfernen = $derived(ich.darf("loeschen"));
  let sichtbar = $derived(!!stand.material.length || !!stand.funde.length || darfHinzu);
  let summe = $derived(stand.material.reduce((s, m) => s + m.groesse, 0));

  // Laden, und neu laden, sobald eine Datei für dieses Buch bei der Annahme weiterkommt
  $effect(() => {
    void stand.kennung;
    void stand.laden();
  });

  async function gewaehlt() {
    const dateien = [...(feld?.files ?? [])];
    if (feld) feld.value = "";
    const zips = dateien.filter((d) => /\.zip$/i.test(d.name));
    let entpacken = false;
    if (zips.length) {
      entpacken = await frage({
        titel: zips.length === 1 ? "ZIP auspacken?" : "ZIP-Dateien auspacken?",
        text: zips.map((z) => z.name).join(", "),
        folgen: ["Auspacken: jede Datei darin wird eigenes Begleitmaterial.", "Als ZIP behalten: sie bleibt eine Datei, wie sie ist."],
        ja: "Auspacken", nein: "Als ZIP behalten", symbol: "box-open", gefahr: false,
      });
    }
    stand.hinzufuegen(dateien, entpacken);
  }
</script>

{#if sichtbar}
  <Karte titel="Begleitmaterial" symbol="paperclip" breit>
    {#snippet neben()}
      {#if darfHinzu}<Knopf text="Hinzufügen" symbol="plus" klein laeuft={stand.unterwegs > 0} titel="Eine oder mehrere Dateien, auch eine ZIP" onclick={() => feld?.click()} />{/if}
    {/snippet}
    {#each stand.funde as f (f.knoten)}
      <div class="fund mulde">
        <Symbol name="magnifying-glass-plus" />
        <span class="name"><b>Datei neben dem Original gefunden, als Begleitmaterial nehmen?</b><br /><span class="leise">{f.name}, {groesse(f.groesse)}</span></span>
        {#if darfUmbenennen}
          <span class="tasten2">
            <Knopf text="Ja" symbol="check" klein haupt gesperrt={stand.arbeitet} titel="{f.name} wird Begleitmaterial dieses Buchs" onclick={() => void stand.fund(f, true)} />
            <Knopf text="Nein" symbol="xmark" klein gesperrt={stand.arbeitet} titel="Sie bleibt, wo sie ist, und wird nicht wieder angeboten" onclick={() => void stand.fund(f, false)} />
          </span>
        {/if}
      </div>
    {/each}
    {#if stand.fehler && !stand.liste}
      <p class="marke-text schlecht"><Symbol name="triangle-exclamation" />{stand.fehler}</p>
    {:else if stand.material.length}
      <div class="materialliste">
        {#each stand.material as m (m.id)}<Materialzeile {m} {stand} {darfUmbenennen} {darfEntfernen} />{/each}
      </div>
    {:else if stand.liste}
      <p class="leise">Noch kein Begleitmaterial. Beispielcode, Übungen, Lösungen, Beilagen und Korrekturen gehören hierher.</p>
    {/if}
    {#if stand.unterwegs}<p class="marke-text info"><Symbol name="circle-notch" dreht />{anzahl(stand.unterwegs, "Datei kommt", "Dateien kommen")} gerade dazu</p>{/if}
    {#if stand.liste && stand.material.length}
      <p class="leise zahl"><Symbol name={stand.liste.ort === "kellerwolke" ? "cloud" : "hard-drive"} /> {anzahl(stand.material.length, "Datei", "Dateien")}, {groesse(summe)}, {stand.liste.ort === "kellerwolke" ? "in der Kellerwolke neben dem Original" : "auf diesem Gerät im Buchordner unter Material"}</p>
    {/if}
    {#if darfHinzu}<input type="file" multiple hidden bind:this={feld} onchange={() => void gewaehlt()} />{/if}
  </Karte>
{/if}
