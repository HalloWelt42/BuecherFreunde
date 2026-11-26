<script lang="ts">
  // Katalog wählen (BF-69): drei Wege als Kacheln, dazu Laden und Sichern als Datei
  import { anzahl } from "../../../lib/format";
  import { GRAUTON } from "../../../lib/katalog";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Katalogzeichen from "../../../lib/teile/Katalogzeichen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import type { Katalogweg } from "../../../lib/typen";
  import { pflege } from "./pflege.svelte";

  let wahlfeld: HTMLInputElement | undefined = $state();
  let besetzt = $derived(pflege.passtAn || !!pflege.beginnt);
  let standardtext = $derived(
    [
      pflege.standard ? `${anzahl(pflege.standard.bereiche, "Bereich", "Bereiche")}, ${anzahl(pflege.standard.kategorien, "Kategorie", "Kategorien")}, für jede Bibliothek.` : "Für jede Bibliothek.",
      "Die Regeln folgen den Sachgruppen der Bibliotheken, dazu Schlagworte und Wörter im Titel, auf Deutsch und Englisch.",
    ].join(" "),
  );

  interface Weg {
    weg: Katalogweg;
    titel: string;
    text: string;
    zeichen: string;
    farbe: string;
    knopf: string;
    symbol: string;
    empfohlen?: boolean;
  }
  let wege = $derived<Weg[]>([
    { weg: "standard", titel: "Standard-Katalog", text: standardtext, zeichen: "sitemap", farbe: "#2f6fb3", knopf: "Übernehmen", symbol: "check" },
    {
      weg: "bestand", titel: "An den Bestand anpassen", zeichen: "wand-magic-sparkles", farbe: "#a87a2a", knopf: "Vorschlag machen", symbol: "wand-magic-sparkles", empfohlen: true,
      text: "Der Standard als Grundlage. Regeln und lokale KI zählen nach: Leere Kategorien bleiben verborgen, große werden geteilt, Fehlendes kommt dazu. Alles kommt als Vorschlag.",
    },
    { weg: "leer", titel: "Leer anfangen", text: "Eigene Bereiche und Kategorien von Grund auf, mit eigenen Regeln.", zeichen: "plus", farbe: GRAUTON, knopf: "Anfangen", symbol: "plus" },
  ]);

  function gewaehlt(e: Event) {
    const feld = e.currentTarget as HTMLInputElement;
    const datei = feld.files?.[0];
    feld.value = "";
    if (datei) void pflege.ladeDatei(datei);
  }
</script>

<Karte titel="Katalog wählen" symbol="sitemap" breit id="katalog-waehlen">
  <div class="katalogwege">
    {#each wege as w (w.weg)}
      <div class="katalogweg platte" class:empfohlen={w.empfohlen}>
        <div class="wegkopf"><Katalogzeichen name={w.zeichen} farbe={w.farbe} groesse="gross" /><b>{w.titel}</b>{#if w.empfohlen}<span class="katalogmarke">Empfohlen</span>{/if}</div>
        <p>{w.text}</p>
        {#if w.weg === "bestand" && pflege.passtAn && pflege.lauf?.schritt}<p class="leise" role="status">{pflege.lauf.schritt}</p>{/if}
        <Knopf text={w.knopf} symbol={w.symbol} haupt={w.empfohlen} laeuft={pflege.beginnt === w.weg || (w.weg === "bestand" && pflege.passtAn)} gesperrt={besetzt} onclick={() => void pflege.waehle(w.weg)} />
      </div>
    {/each}
  </div>
  <div class="reihe dateitasten">
    <Knopf text="Katalog laden" symbol="file-import" gesperrt={besetzt} onclick={() => wahlfeld?.click()} />
    <Knopf text="Katalog sichern" symbol="file-export" gesperrt={!pflege.hatKatalog} onclick={() => void pflege.sichere()} />
    <span class="leise">als Datei, etwa zum Teilen mit anderen</span>
  </div>
  <input type="file" accept=".json,application/json" hidden aria-label="Katalog-Datei wählen" bind:this={wahlfeld} onchange={gewaehlt} />
</Karte>
