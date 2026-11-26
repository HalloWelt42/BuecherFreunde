<script lang="ts">
  // Was vom Ordner eingelesen wird: Zahlen, Balken, jede Datei mit ihrem Stand (Einträge der Annahme aus Ordnern)
  import type { AnnahmeEintrag } from "../../../lib/annahme/typen";
  import type { Sammellage } from "../../../lib/annahme/sammlung";
  import { zahl } from "../../../lib/format";
  import { annahme } from "../../../lib/stand/annahme.svelte";
  import { auftraege } from "../../../lib/stand/auftraege.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  const lagen: Record<Sammellage, [string, string, string]> = {
    wartet: ["hourglass-half", "info", "Wartet"], laeuft: ["circle-notch", "info", "Läuft"], fertig: ["circle-check", "gut", "Fertig"], fehler: ["triangle-exclamation", "schlecht", "Gescheitert"], da: ["clone", "info", "Schon da"],
  };

  let s = $derived(annahme.einlesen);
  let ruhig = $derived(!s.laeuft && s.erledigt > 0);
  let lage = (a: AnnahmeEintrag): Sammellage => s.lagen.get(a.id) ?? "wartet";

  async function tun(was: () => Promise<void>) {
    try {
      await was();
    } catch (e) {
      melde.schlecht(e);
    }
  }

  function text(a: AnnahmeEintrag): string {
    const l = lage(a);
    if (l === "fehler") return a.text || "ohne Angabe";
    if (l === "laeuft") return a.text || "wird eingelesen";
    if (l === "da") return a.text || "steht schon in der Bibliothek, nichts kopiert";
    return "";
  }
</script>

<Karte titel="Eingelesene Dateien" symbol="file-import">
  {#snippet neben()}
    {#if s.wartend > 0}<Knopf text="Wartende anhalten" symbol="stop" klein titel="Was gerade läuft, läuft noch zu Ende" onclick={() => void tun(() => auftraege.einlesenAbbrechen())} />{/if}
    {#if ruhig}<Knopf text="Fertige ausblenden" symbol="broom" klein frei onclick={() => void tun(() => auftraege.bereinigen())} />{/if}
  {/snippet}
  <Balken anteil={s.gesamt ? s.erledigt / s.gesamt : 0} gut={!s.laeuft && !s.gescheitert} name="Einlesen" />
  <p class="leise zahl">{zahl(s.erledigt)} von {zahl(s.gesamt)}: {zahl(s.imRegal)} fertig{s.da ? `, ${zahl(s.da)} schon da` : ""}{s.gescheitert ? `, ${zahl(s.gescheitert)} gescheitert` : ""}{s.gesamt - s.erledigt ? `, ${zahl(s.gesamt - s.erledigt)} offen` : ""}</p>
  <ul class="aufgaben">
    {#each s.eintraege as a (a.id)}
      {@const [symbol, ton, wort] = lagen[lage(a)]}
      <li><span class="marke-text {ton}"><Symbol name={symbol} dreht={lage(a) === "laeuft"} /></span><span class="name"><b>{a.name}</b><br /><span class="marke-text {ton}">{wort}</span> <span class="klein">{text(a)}</span></span>{#if a.buch_id}<Knopf text="Buch öffnen" symbol="book-open" klein href="/book/{a.buch_id}" />{/if}</li>
    {/each}
  </ul>
</Karte>

<style>
  .aufgaben {
    display: grid;
    max-height: 22rem;
    overflow: auto;
  }
  li {
    display: grid;
    grid-template-columns: 1.5rem minmax(0, 1fr) auto;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4375rem 0;
    border-top: 1px solid var(--linie);
  }
  .name {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  b {
    font-weight: 600;
  }
</style>
