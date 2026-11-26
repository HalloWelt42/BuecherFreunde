<script lang="ts">
  // Schritt Katalog: der mitgelieferte, leer beginnen oder später ein Vorschlag aus dem Bestand. Ein Tipp wählt; unter Wartung
  // nur vorgemerkt. Gelöscht wird nichts, gleiche Schlüssel ändern sich.
  import { untrack } from "svelte";
  import { waehleKatalog, type Katalogwahl, type Schritt } from "../../lib/api/einrichtung";
  import { ladeStandard } from "../../lib/api/katalog";
  import { katalogwahlAus } from "../../lib/einrichtung/ablauf";
  import { anzahl } from "../../lib/format";
  import { GRAUTON, umfang } from "../../lib/katalog";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Kachel from "./Kachel.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let gewaehlt = $state<Katalogwahl | null>(untrack(() => katalogwahlAus(schritt.text)));
  let vorgemerkt = $state(false);
  let standard = $state<{ bereiche: number; kategorien: number } | null>(null);

  $effect(() => {
    ladeStandard().then((k) => (standard = umfang(k.bereiche))).catch(() => {});
  });

  let wege = $derived<[Katalogwahl, string, string, string, string, string][]>([
    ["standard", "sitemap", "#2f6fb3", "Mitgelieferter Katalog",
      `${standard ? `${anzahl(standard.bereiche, "Bereich", "Bereiche")}, ${anzahl(standard.kategorien, "Kategorie", "Kategorien")}, ` : ""}Regeln nach den Sachgruppen der Bibliotheken.`, "Empfohlen"],
    ["leer", "plus", GRAUTON, "Leer beginnen", "Eigene Bereiche und Kategorien von Grund auf.", ""],
    ["bestand", "wand-magic-sparkles", "#a87a2a", "Später aus dem Bestand", "Erst der mitgelieferte, sobald Bücher da sind ein Vorschlag nach dem Bestand.", ""],
  ]);

  let offen = $derived(!gewaehlt && schritt.stand !== "erledigt" && !einrichtung.wartung);

  async function waehle(wahl: Katalogwahl) {
    const v = await waehleKatalog(wahl);
    gewaehlt = wahl;
    vorgemerkt = !v.angewandt;
    if (v.angewandt) await einrichtung.laden();
  }
</script>

<!-- Unter Wartung heißt Weiter ohne Wahl: der Katalog bleibt, wie er ist -->
<Schrittrahmen ueberspringen={!schritt.pflicht} weiter={{ gesperrt: offen, titel: offen ? "Erst einen Katalog wählen, sonst überspringen" : undefined }}>
  <p class="leise">Bereiche und Kategorien, nach denen die Bücher eingeordnet werden.</p>
  <div class="ew-kacheln drei">
    {#each wege as [wahl, symbol, farbe, titel, text, marke] (wahl)}
      <Kachel {symbol} {farbe} {titel} {text} {marke} pfeil={false} gedrueckt={gewaehlt === wahl} gesperrt={einrichtung.arbeitet}
        onclick={() => void einrichtung.tu(() => waehle(wahl), "Katalog nicht gewählt")} />
    {/each}
  </div>
  {#if vorgemerkt}<p class="marke-text info"><Symbol name="clock" />Vorgemerkt, gilt erst nach dem Übernehmen.</p>{/if}
</Schrittrahmen>
