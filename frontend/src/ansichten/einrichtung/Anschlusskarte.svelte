<script lang="ts">
  // Ein Anschluss: Adresse, Schlüssel einmal einfügen, "Verbindung prüfen". Mit neuer Adresse oder neuem Schlüssel trägt Prüfen
  // ein, was besteht (der Server legt den Schlüssel in seiner Schlüsseldatei ab); sonst prüft es nur. Danach steht nur noch
  // "eingetragen" und "Ersetzen" da, nie der Schlüssel selbst. Unter Wartung ist das Eintragen nur vorgemerkt.
  import { untrack, type Snippet } from "svelte";
  import { pruefeAnschluss, trageAnschlussEin, type Anschluss, type Verbindungspruefung } from "../../lib/api/einrichtung";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Lampe from "../../lib/teile/Lampe.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  /** `children`: was zum Anschluss gehört, etwa die Sicherungen in der Kellerwolke */
  let { anschluss, ongeaendert, children = undefined }: { anschluss: Anschluss; ongeaendert: () => Promise<void>; children?: Snippet } = $props();

  const ZEICHEN = { kellerwolke: "cloud", leitstelle: "tower-broadcast", vertonung: "volume-high", nachschlag: "book-atlas" };
  const PLATZHALTER = { kellerwolke: "https://wolke.beispiel.lan", leitstelle: "https://leitstelle.beispiel.lan", vertonung: "https://vertonung.beispiel.lan",
    nachschlag: "https://nachschlag.beispiel.lan" };

  let adresse = $state(untrack(() => anschluss.adresse));
  let schluessel = $state("");
  let ersetzen = $state(false);
  let laeuft = $state(false);
  let fehler = $state("");
  let vorgemerkt = $state(false);
  /** Die Prüfung eben; sonst die letzte des Servers seit seinem Start */
  let eben = $state<Verbindungspruefung | null>(null);

  let pruefung = $derived(eben ?? anschluss.pruefung);
  let mitSchluessel = $derived(anschluss.schluessel !== null);
  let eingetragen = $derived(!!anschluss.schluessel?.eingetragen && !ersetzen);
  let neu = $derived(adresse.trim().replace(/\/+$/, "") !== anschluss.adresse || !!schluessel.trim());

  async function pruefe() {
    laeuft = true;
    fehler = "";
    try {
      if (neu) {
        const v = await trageAnschlussEin(anschluss.art, adresse.trim(), schluessel.trim() || undefined);
        vorgemerkt = !v.angewandt;
        schluessel = "";
        ersetzen = false;
        eben = null;
        await ongeaendert();
      } else {
        eben = await pruefeAnschluss(anschluss.art, {});
      }
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
      eben = null;
    } finally {
      laeuft = false;
    }
  }
</script>

<Karte titel={anschluss.name} symbol={ZEICHEN[anschluss.art]}>
  {#if anschluss.hinweis && anschluss.art !== "kellerwolke"}<p class="leise">{anschluss.hinweis}</p>{/if}
  <div class="zweifeld">
    <label class="feld">Adresse<input class="eingabe" type="url" placeholder={PLATZHALTER[anschluss.art]} autocomplete="off" spellcheck="false" bind:value={adresse} disabled={laeuft} /></label>
    {#if !mitSchluessel}
      <div class="feld"><span>Schlüssel</span><span class="leise">nicht nötig</span></div>
    {:else if eingetragen}
      <div class="feld"><span>Schlüssel</span>
        <div class="mulde ew-schluessel">
          <span class="marke-text gut"><Symbol name="circle-check" />{anschluss.schluessel?.vorgemerkt ? "vorgemerkt" : "eingetragen"}</span>
          <Knopf text="Ersetzen" symbol="key" klein frei titel="Schlüssel {anschluss.name === 'Kellerwolke' ? 'der Kellerwolke' : 'der Leitstelle'} ersetzen" onclick={() => (ersetzen = true)} />
        </div>
      </div>
    {:else}
      <label class="feld">Schlüssel<input class="eingabe" type="password" autocomplete="off" spellcheck="false" aria-label="Schlüssel: {anschluss.name}" bind:value={schluessel} disabled={laeuft} /></label>
    {/if}
  </div>
  <div class="ew-pruefzeile">
    <Knopf text="Verbindung prüfen" symbol="stethoscope" klein {laeuft} gesperrt={!adresse.trim() || einrichtung.arbeitet} onclick={() => void pruefe()} />
    {#if laeuft && schluessel.trim()}
      <span class="leise">Der Server prüft den Schlüssel und legt ihn in seiner Schlüsseldatei ab.</span>
    {:else if fehler}
      <span class="ew-ergebnis"><Lampe stand="schlecht" text={fehler} /></span>
    {:else if pruefung}
      <span class="ew-ergebnis"><Lampe stand={pruefung.ok ? "gut" : "schlecht"} text={pruefung.ok ? pruefung.text || "antwortet" : pruefung.grund} /></span>
    {:else if !anschluss.adresse}
      <Lampe stand="aus" text="nicht eingerichtet" />
    {/if}
  </div>
  {#if vorgemerkt}<p class="marke-text info"><Symbol name="clock" />Vorgemerkt, gilt erst nach dem Übernehmen.</p>{/if}
  <!-- Bei der Kellerwolke ist der Hinweis der zum Persönlichen: wer sie verwaltet, könnte es lesen -->
  {#if anschluss.hinweis && anschluss.art === "kellerwolke"}<p class="leise ew-hinweiszeile"><Symbol name="eye" /><span>{anschluss.hinweis}</span></p>{/if}
  {@render children?.()}
</Karte>
