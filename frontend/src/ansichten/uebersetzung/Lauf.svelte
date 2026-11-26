<script lang="ts">
  // Der Auftrag einer Übersetzung (BF-71, Entwurf Abschnitt 3): Zeiten, Fortschritt, sechs Stationen, Tempo und die Kapitel
  // mit Dauer. Kopf und Tasten bleiben stehen, nur die Kapitel rollen. Solange er läuft, kommt der Stand alle paar Sekunden.
  import { untrack } from "svelte";
  import { brecheLaufAb, holeLaufstand, pausiereLauf, setzeLaufFort } from "../../lib/api/uebersetzung";
  import { anzahl, zahl } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import { uebersetzungen } from "../../lib/stand/uebersetzungen.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { STATIONSZEICHEN, kapiteldauer, kapitelstandtext, kapitelzeilen, laufanteil, laufort, stationstext } from "../../lib/uebersetzung/texte";
  import type { Laufstand } from "../../lib/uebersetzung/typen";
  import { dauer, etwa, zeitKurz } from "../../lib/uebersetzung/zeiten";
  import { Buchuebersetzung } from "./fassung.svelte";

  let { params }: { params: Record<string, string> } = $props();

  const TAKT_MS = 2500;
  const bezug = new Buchuebersetzung(untrack(() => Number(params.id)));
  let stand = $state<Laufstand | null>(null);
  let fehler = $state("");
  let arbeitet = $state<"" | "pause" | "fortsetzen" | "abbrechen">("");
  let uhr: ReturnType<typeof setTimeout> | undefined;

  async function hole() {
    clearTimeout(uhr);
    const f = bezug.deutsch;
    if (!f) return;
    try {
      stand = await holeLaufstand(f.id);
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
    if (stand?.stand === "laeuft") uhr = setTimeout(() => void hole(), TAKT_MS);
  }

  $effect(() => {
    void bezug.laden().then(hole);
    return () => clearTimeout(uhr);
  });

  async function tue(was: typeof arbeitet, tun: (fassung: number) => Promise<Laufstand>, vorab: string) {
    const f = bezug.deutsch;
    if (!f) return;
    arbeitet = was;
    try {
      stand = await tun(f.id);
    } catch (e) {
      melde.schlecht(e, vorab);
    } finally {
      arbeitet = "";
    }
    void uebersetzungen.auffrischen();
    void hole();
  }

  async function abbrechen() {
    if (!stand) return;
    const z = stand.zahlen;
    const ja = await frage({
      titel: "Übersetzung abbrechen?",
      folgen: [`${zahl(z.uebersetzt)} von ${anzahl(z.bloecke, "Block", "Blöcken")} sind deutsch und bleiben lesbar.`, "Was noch fehlt, steht im Original. Fortsetzen übersetzt es später weiter."],
      ja: "Übersetzung abbrechen", nein: "Nicht abbrechen", symbol: "xmark", gefahr: false,
    });
    if (ja) await tue("abbrechen", brecheLaufAb, "Nicht abgebrochen");
  }

  let titel = $derived(bezug.buch?.title ?? "");
  let laeuft = $derived(stand?.stand === "laeuft");
  let zeilen = $derived(stand ? kapitelzeilen(stand.kapitel) : { einzeln: [], rest: null });
  let nachZeit = $derived(stand && stand.bisher_s > 0);
  const ENDE: Record<string, string> = { pause: "Pause", fehler: "Fehler", teilweise: "abgebrochen", fertig: "fertig" };
  const KAPITELZEICHEN = { fertig: "circle-check", laeuft: "spinner", wartet: "clock" };
</script>

<div class="werkzeug">
  <Knopf text="Zum Buch" symbol="arrow-left" klein href="/book/{bezug.id}" />
  <h1>Auftrag</h1>
</div>

<div class="inhalt rollen">
  {#if fehler && !stand}
    <Zustand art="fehler" text={fehler} onerneut={() => void hole()} />
  {:else if bezug.fehler}
    <Zustand art="fehler" text={bezug.fehler} onerneut={() => void bezug.laden().then(hole)} />
  {:else if bezug.geladen && !bezug.deutsch}
    <Zustand text="Dieses Buch wird noch nicht übersetzt."><Knopf text="Zum Buch" symbol="arrow-left" klein href="/book/{bezug.id}" /></Zustand>
  {:else if !stand}
    <Zustand art="laedt" text="Stand wird geladen" />
  {:else}
    <section class="laufkarte platte fuellt" aria-label="Auftrag">
      <div class="reihe laufkopf">
        <b>Übersetzen: {titel}</b>
        {#if laufort(stand)}<span class="leise zahl">{laufort(stand)}</span>{/if}
        <span class="schiebt reihe">
          {#if laeuft}
            <Knopf text="Pause" symbol="pause" klein laeuft={arbeitet === "pause"} gesperrt={!!arbeitet} onclick={() => void tue("pause", pausiereLauf, "Keine Pause")} />
          {:else if stand.stand !== "fertig"}
            <Knopf text="Fortsetzen" symbol="play" klein laeuft={arbeitet === "fortsetzen"} gesperrt={!!arbeitet} onclick={() => void tue("fortsetzen", setzeLaufFort, "Nicht fortgesetzt")} />
          {/if}
          {#if ["laeuft", "pause", "fehler"].includes(stand.stand)}
            <Knopf text="Abbrechen" symbol="xmark" klein frei laeuft={arbeitet === "abbrechen"} gesperrt={!!arbeitet} onclick={() => void abbrechen()} />
          {/if}
        </span>
      </div>
      {#if stand.grund}<span class="marke-text warn"><Symbol name="circle-exclamation" />{stand.grund}</span>{/if}
      <div class="laufzeiten">
        <div class="laufzeit"><small>Begonnen</small><b>{zeitKurz(stand.begonnen) || "noch nicht"}</b></div>
        <div class="laufzeit"><small>Bisher</small><b>{dauer(stand.bisher_s)}</b></div>
        <div class="laufzeit"><small>Noch etwa</small><b>{stand.stand === "fertig" ? "nichts mehr" : etwa(stand.noch_s)}</b></div>
        <!-- Fertig gegen nur, solange er läuft; sonst steht hier, wie er steht -->
        <div class="laufzeit"><small>{laeuft ? "Fertig gegen" : "Stand"}</small><b>{laeuft ? zeitKurz(stand.fertig_gegen) : ENDE[stand.stand]}</b></div>
      </div>
      <Balken anteil={laufanteil(stand)} gut={stand.stand === "fertig"} name="Fortschritt der Übersetzung" />
      <div class="laufstationen">
        {#each stand.stationen as s (s.name)}
          <div class="laufstation {s.stand}">
            <b><Symbol name={s.stand === "fertig" ? "circle-check" : s.stand === "laeuft" ? STATIONSZEICHEN[s.name] : "clock"} />{s.name}</b>
            <small title={s.text}>{stationstext(s)}</small>
          </div>
        {/each}
      </div>
      <span class="leise zahl">
        {nachZeit ? "Tempo dieses Laufs" : "Tempo geschätzt"}: {zahl(Math.round(stand.tempo_s_je_seite))} Sekunden je Seite mit Prüfung.{#if laeuft}{" "}Die Schätzung rechnet damit und wird mit jedem Kapitel genauer.{/if}
      </span>
      {#if stand.kapitel.length}
        <div class="kapitelliste rollen" role="table" aria-label="Kapitel">
          <div class="kapitelzeile kopf" role="row"><span></span><span>Kapitel</span><span>Stand</span><span class="zahl">Dauer</span><span class="zahl">geprüft</span><span class="zahl">nach&shy;gearbeitet</span><span class="zahl">offen</span></div>
          {#each zeilen.einzeln as k, n (k.nr)}
            <div class="kapitelzeile" role="row">
              <Symbol name={KAPITELZEICHEN[k.stand]} klasse={k.stand === "wartet" ? "leise" : k.stand} />
              <span class="titel" title={k.titel}>{n + 1}. {k.titel}</span>
              <span class="leise">{kapitelstandtext(k)}</span>
              <span class="zahl leise">{kapiteldauer(k)}</span>
              <span class="zahl">{zahl(k.geprueft)}</span>
              <span class="zahl">{zahl(k.nachgearbeitet)}</span>
              <span class="zahl" class:offen={k.offen > 0}>{zahl(k.offen)}</span>
            </div>
          {/each}
          {#if zeilen.rest}
            <div class="kapitelzeile rest" role="row">
              <span></span><span class="titel leise">{zeilen.rest.von} bis {zeilen.rest.bis}</span><span class="leise">warten</span>
              <span class="zahl leise">{kapiteldauer({ dauer_s: zeilen.rest.dauer_s, geschaetzt: true })}</span><span></span><span></span><span></span>
            </div>
          {/if}
        </div>
      {/if}
    </section>
  {/if}
</div>
