<script lang="ts">
  // Was vom Ordner eingelesen wird: Zahlen, Balken, jede Datei mit ihrem Stand
  import { zahl } from "../../../lib/format";
  import { auftraege, type Einleseaufgabe } from "../../../lib/stand/auftraege.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import Balken from "../../../lib/teile/Balken.svelte";
  import Karte from "../../../lib/teile/Karte.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  const lagen: Record<Einleseaufgabe["status"], [string, string, string]> = {
    wartend: ["hourglass-half", "info", "Wartet"], verarbeite: ["circle-notch", "info", "Läuft"], fertig: ["circle-check", "gut", "Fertig"], fehler: ["triangle-exclamation", "schlecht", "Gescheitert"], duplikat: ["clone", "info", "Schon da"],
  };

  let z = $derived(auftraege.zaehler);
  let erledigt = $derived(z.fertig + z.duplikat + z.fehler);
  let ruhig = $derived(!auftraege.einlesenLaeuft && erledigt > 0);

  async function tun(was: () => Promise<void>) {
    try {
      await was();
    } catch (e) {
      melde.schlecht(e);
    }
  }

  function text(a: Einleseaufgabe): string {
    if (a.status === "fehler") return a.error || "ohne Angabe";
    if (a.status === "verarbeite") return `${a.current_step || "wird eingelesen"}, ${a.progress_percent} %`;
    if (a.status === "duplikat") return a.error || "steht schon in der Bibliothek, nichts kopiert";
    return "";
  }
</script>

<Karte titel="Eingelesene Dateien" symbol="file-import">
  {#snippet neben()}
    {#if z.wartend > 0}<Knopf text="Wartende anhalten" symbol="stop" klein titel="Was gerade läuft, läuft noch zu Ende" onclick={() => void tun(() => auftraege.einlesenAbbrechen())} />{/if}
    {#if ruhig}<Knopf text="Fertige ausblenden" symbol="broom" klein frei onclick={() => void tun(() => auftraege.bereinigen())} />{/if}
  {/snippet}
  <Balken anteil={z.gesamt ? erledigt / z.gesamt : 0} gut={!auftraege.einlesenLaeuft && !z.fehler} name="Einlesen" />
  <p class="leise zahl">{zahl(erledigt)} von {zahl(z.gesamt)}: {zahl(z.fertig)} fertig{z.duplikat ? `, ${zahl(z.duplikat)} schon da` : ""}{z.fehler ? `, ${zahl(z.fehler)} gescheitert` : ""}{z.verarbeite + z.wartend ? `, ${zahl(z.verarbeite + z.wartend)} offen` : ""}</p>
  <ul class="aufgaben">
    {#each auftraege.aufgaben as a (a.id)}
      {@const [symbol, ton, wort] = lagen[a.status] ?? lagen.fehler}
      <li><span class="marke-text {ton}"><Symbol name={symbol} dreht={a.status === "verarbeite"} /></span><span class="name"><b>{a.filename}</b><br /><span class="marke-text {ton}">{wort}</span> <span class="klein">{text(a)}</span></span>{#if a.book_id}<Knopf text="Buch öffnen" symbol="book-open" klein href="/book/{a.book_id}" />{/if}</li>
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
