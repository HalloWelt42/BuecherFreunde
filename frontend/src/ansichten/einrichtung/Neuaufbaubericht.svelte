<script lang="ts">
  // Bericht nach dem Neuaufbau: übernommen, ohne Auszug, Fehler. Bücher ohne Auszug sind im Bestand; Angaben und Volltext
  // entstehen neu aus der Datei, persönliche Daten gibt es für sie keine. Gelöscht wird nichts.
  import { ladeNeuaufbaubericht, type Neuaufbaubericht, type Ohneauszug } from "../../lib/api/einrichtung";
  import { anzahl, zahl } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";
  import Zaehler from "./Zaehler.svelte";

  const ZEIGEN = 3;
  const DATEIZEICHEN: Record<string, string> = { pdf: "file-pdf", epub: "book", mobi: "book", txt: "file-lines", md: "file-lines", zip: "file-zipper" };

  let bericht = $state<Neuaufbaubericht | null>(null);
  let fehler = $state("");

  async function lade() {
    try {
      bericht = await ladeNeuaufbaubericht();
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade());

  const zeichen = (name: string) => DATEIZEICHEN[name.split(".").pop()?.toLowerCase() ?? ""] ?? "file";
  const ordner = (pfad: string) => pfad.split("/").slice(0, -1).join("/") || pfad;
</script>

{#snippet dateien(liste: Ohneauszug[])}
  {#each liste.slice(0, ZEIGEN) as d (d.pfad)}
    <div class="ew-buchzeile"><span class="ew-dateizeichen"><Symbol name={zeichen(d.name)} /></span><span class="ew-mitte"><b>{d.name}</b><small class="pfad">{ordner(d.pfad)}</small></span></div>
  {/each}
  {#if liste.length > ZEIGEN}<p class="leise zahl">und {zahl(liste.length - ZEIGEN)} weitere</p>{/if}
{/snippet}

<Schrittrahmen weiter={{ text: "Zur Bibliothek", symbol: "book-bookmark", tun: () => einrichtung.abschliessen() }}>
  {#if bericht}
    <Zaehler werte={[["gut", bericht.mit_auszug, "übernommen"], ["warn", bericht.ohne_auszug.length, "ohne Auszug"], [bericht.fehler.length ? "schlecht" : "aus", bericht.fehler.length, "Fehler"]]} />
    <p class="marke-text info"><Symbol name="shield-halved" />Nichts gelöscht.</p>
    {#if bericht.ohne_auszug.length}
      <section class="ew-buecher">
        <h3 class="ew-gruppe-kopf"><Symbol name="file-circle-question" />Ohne Auszug <span class="leise zahl">{zahl(bericht.ohne_auszug.length)}</span></h3>
        <p class="leise">Im Bestand. Angaben und Volltext entstehen neu aus der Datei, persönliche Daten gibt es für sie keine.</p>
        {@render dateien(bericht.ohne_auszug)}
      </section>
    {/if}
    {#if bericht.fehler.length}
      <section class="ew-buecher">
        <h3 class="ew-gruppe-kopf"><Symbol name="circle-xmark" />Fehler <span class="leise zahl">{zahl(bericht.fehler.length)}</span></h3>
        {@render dateien(bericht.fehler)}
      </section>
    {/if}
    <section>
      <h3 class="ew-gruppe-kopf"><Symbol name="user-pen" />Profile <span class="leise zahl">{zahl(bericht.profile)}</span></h3>
      <p class="leise">{bericht.profile ? `${anzahl(bericht.profile, "Profil", "Profile")} mit dem Persönlichen je Buch, ohne PIN und Bild-PIN; die setzt du unter Einstellungen, Familie neu.` : "Keine Profile aus der Kellerwolke."}</p>
    </section>
  {:else if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
  {:else}
    <Zustand art="laedt" text="Bericht wird geholt" />
  {/if}
</Schrittrahmen>
