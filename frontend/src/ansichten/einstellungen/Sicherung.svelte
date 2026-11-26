<script lang="ts">
  // Sicherung: anlegen, herunterladen und zurückspielen (BF-82). Zurückspielen zeigt erst die Folgen (der Bestand wird ersetzt,
  // vorher entsteht eine Sicherung des jetzigen Stands) und läuft dann als Auftrag "Sicherung einspielen". Gelöscht wird nichts.
  import { onDestroy, onMount } from "svelte";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { sicherungAdresse } from "../../lib/api/config";
  import { ladeWiederherstellfolgen, ladeWiederherstellstand, stelleWiederHer, type Hochladestand, type Sicherungsquelle, type Wiederherstellstand } from "../../lib/api/einrichtung";
  import { TEILZEICHEN } from "../../lib/einrichtung/ablauf";
  import { laeuftNoch, sicherungszeile, wiederherstellfolgen } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { anzahl, groesse } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Auftragsfeld from "../einrichtung/Auftragsfeld.svelte";
  import Sicherungsdatei from "../einrichtung/Sicherungsdatei.svelte";
  import { vorgaenge } from "./vorgaenge.svelte";

  $effect(() => void vorgaenge.ladeSicherungen());

  // Die Liste trägt die Ortszeit des Servers
  const wann = (z: string) => new Date(z).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

  let einspielen = $state<Wiederherstellstand | null>(null);
  let ausDatei = $state(false);
  let halt: (() => void) | null = null;

  function beobachte() {
    halt?.();
    halt = imTakt(async () => {
      einspielen = await ladeWiederherstellstand();
      // Fertig: die Sicherung des Stands davor steht jetzt in der Liste
      if (!laeuftNoch(einspielen.auftrag)) void vorgaenge.ladeSicherungen();
      return laeuftNoch(einspielen.auftrag);
    }, 1500);
  }

  // Läuft ein Zurückspielen schon (die Seite war zu), steht sein Stand gleich da
  onMount(() => {
    ladeWiederherstellstand().then((s) => {
      if (!laeuftNoch(s.auftrag)) return;
      einspielen = s;
      beobachte();
    }).catch(() => {});
  });
  onDestroy(() => halt?.());

  async function spiele(quelle: Sicherungsquelle, kennung: string) {
    try {
      const f = await ladeWiederherstellfolgen("laufend", quelle, kennung);
      const ja = await frage({
        titel: "Aus dieser Sicherung zurückspielen?",
        text: [f.sicherung.name, sicherungszeile(f.sicherung)].filter(Boolean).join(", "),
        folgen: wiederherstellfolgen(f, true),
        ja: "Zurückspielen",
        symbol: "clock-rotate-left",
      });
      if (!ja) return;
      const auftrag = await stelleWiederHer("laufend", quelle, kennung, f.stand);
      einspielen = { auftrag, ergebnis: null };
      ausDatei = false;
      beobachte();
    } catch (e) {
      melde.schlecht(e, "Nicht zurückgespielt");
    }
  }

  let laeuft = $derived(laeuftNoch(einspielen?.auftrag ?? null));
</script>

<p class="klein">Sichert Datenbank, Einstellungen und Angaben als eine Datei. Die Bücher selbst {anschluesse.inWolke ? "liegen in der Kellerwolke" : "liegen im Speicher der App"} und sind nicht enthalten.</p>
{#if vorgaenge.sicherungen?.length}
  {#each vorgaenge.sicherungen as s (s.filename)}
    <div class="stelle zeile-stand eins-knopf">
      <span><b class="dateiname">{s.filename}</b><br /><span class="leise zahl">{wann(s.created_at)}, {groesse(s.size)}</span></span>
      <span class="reihe">
        <Knopf text="Zurückspielen" symbol="clock-rotate-left" nur klein frei gesperrt={laeuft} onclick={() => void spiele("geraet", s.filename)} />
        <Knopf text="Herunterladen" symbol="download" nur klein frei href={sicherungAdresse(s.filename)} download={s.filename} />
      </span>
    </div>
  {/each}
{:else}
  <p class="leise">{vorgaenge.sicherungen ? "Noch keine Sicherung vorhanden." : "Die Liste der Sicherungen kam nicht an."}</p>
{/if}
{#if einspielen}
  <Auftragsfeld auftrag={einspielen.auftrag} wort="Abschnitten fertig" teile={TEILZEICHEN.einspielen} onneu={(a) => einspielen && (einspielen = { ...einspielen, auftrag: a })} />
  {#if einspielen.ergebnis && einspielen.auftrag.stand === "fertig"}
    {@const e = einspielen.ergebnis}
    <p class="marke-text gut"><Symbol name="circle-check" />Zurückgespielt: {e.name}, {anzahl(e.buecher, "Buch", "Bücher")}, {anzahl(e.profile, "Profil", "Profile")}.{#if e.vorher}{" "}Vorher gesichert als {e.vorher}.{/if}</p>
    <div class="reihe"><Knopf text="Neu laden" symbol="rotate-right" klein onclick={() => location.reload()} /></div>
  {/if}
{/if}
{#if ausDatei}<Sicherungsdatei onfertig={(h: Hochladestand) => void spiele("datei", h.id)} />{/if}
<div class="reihe">
  <Knopf text="Jetzt sichern" symbol="floppy-disk" klein laeuft={vorgaenge.laeuft.sicherung} onclick={() => void vorgaenge.sichere()} />
  <Knopf text="Aus Datei zurückspielen" symbol="file-arrow-up" klein aufgeklappt={ausDatei} gesperrt={laeuft} onclick={() => (ausDatei = !ausDatei)} />
</div>
