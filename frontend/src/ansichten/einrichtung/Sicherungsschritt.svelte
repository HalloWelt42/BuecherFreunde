<script lang="ts">
  // Schritt Sicherung (Aus Sicherung wiederherstellen): eine Datei hochladen, eine aus dem Sicherungsordner oder aus der
  // Kellerwolke wählen. Vor dem Einspielen kommt die Rückfrage mit den Folgen, dann läuft "Sicherung einspielen" als Auftrag.
  // Danach gibt es das Konto aus der Sicherung, der Assistent fragt nach der Anmeldung.
  import { onDestroy, onMount } from "svelte";
  import { ApiError } from "../../lib/api/client";
  import {
    ladeAnschluesse, ladeSicherungsliste, ladeWiederherstellfolgen, ladeWiederherstellstand, stelleWiederHer, type Anschluss, type Auftragsstand,
    type Hochladestand, type Schritt, type Sicherung, type Sicherungsliste, type Sicherungsquelle,
  } from "../../lib/api/einrichtung";
  import { TEILZEICHEN } from "../../lib/einrichtung/ablauf";
  import { laeuftNoch, sicherungszeile, wiederherstellfolgen } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Anschlusskarte from "./Anschlusskarte.svelte";
  import Auftragsfeld from "./Auftragsfeld.svelte";
  import Hinweis from "./Hinweis.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";
  import Sicherungsdatei from "./Sicherungsdatei.svelte";
  import Sicherungszeile from "./Sicherungszeile.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  const QUELLEN: [Sicherungsquelle, string, string, string][] = [
    ["datei", "file-arrow-up", "Datei hochladen", "eine Sicherung als ZIP"],
    ["geraet", "folder-open", "Sicherungsordner", "auf diesem Gerät"],
    ["kellerwolke", "cloud", "Kellerwolke", "Sicherungen der App dort"],
  ];

  let quelle = $state<Sicherungsquelle>("geraet");
  let listen = $state<Partial<Record<"geraet" | "kellerwolke", Sicherungsliste>>>({});
  let wolke = $state<Anschluss | null>(null);
  let gewaehlt = $state<Sicherung | null>(null);
  let auftrag = $state<Auftragsstand | null>(null);
  let fehler = $state("");

  async function liste(q: "geraet" | "kellerwolke") {
    try {
      listen[q] = await ladeSicherungsliste(q);
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  async function wolkeLaden() {
    wolke = (await ladeAnschluesse().catch(() => [] as Anschluss[])).find((a) => a.art === "kellerwolke") ?? null;
    await liste("kellerwolke");
  }

  $effect(() => {
    if (quelle === "geraet" && !listen.geraet) void liste("geraet");
    if (quelle === "kellerwolke" && !listen.kellerwolke) void wolkeLaden();
  });

  /** Fragt nach, bis das Einspielen fertig ist; danach gilt das Konto aus der Sicherung und der Assistent fragt nach der Anmeldung */
  let halt: (() => void) | null = null;
  function beobachte() {
    halt?.();
    halt = imTakt(async () => {
      try {
        const neu = await ladeWiederherstellstand();
        auftrag = neu.auftrag;
        if (!laeuftNoch(neu.auftrag)) await einrichtung.laden();
        return laeuftNoch(neu.auftrag);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) await einrichtung.laden();
        return false;
      }
    }, 1500);
  }

  // Läuft das Einspielen schon (nach einem Neustart der Seite), steht gleich sein Stand da
  onMount(() => {
    ladeWiederherstellstand()
      .then((s) => {
        if (!s.auftrag.stand) return;
        auftrag = s.auftrag;
        if (laeuftNoch(s.auftrag)) beobachte();
      })
      .catch(() => {});
  });
  onDestroy(() => halt?.());

  function ausDatei(h: Hochladestand) {
    gewaehlt = { quelle: "datei", kennung: h.id, name: h.name, groesse: h.groesse, angelegt_am: null, buecher: null, profile: null, version: "" };
  }

  async function wiederherstellen() {
    const s = gewaehlt;
    if (!s) return;
    const f = await ladeWiederherstellfolgen("einrichtung", s.quelle, s.kennung);
    const ja = await frage({
      titel: "Aus dieser Sicherung wiederherstellen?",
      text: [f.sicherung.name, sicherungszeile(f.sicherung)].filter(Boolean).join(", "),
      folgen: wiederherstellfolgen(f),
      ja: "Wiederherstellen",
      symbol: "clock-rotate-left",
      gefahr: f.ersetzt.length > 0,
    });
    if (!ja) return;
    auftrag = await stelleWiederHer("einrichtung", s.quelle, s.kennung, f.stand);
    beobachte();
  }

  let laeuft = $derived(laeuftNoch(auftrag));
  let fertig = $derived(schritt.stand === "erledigt");
</script>

{#snippet sicherungen(l: Sicherungsliste | undefined, ort: string)}
  {#if !l}
    <Zustand art="laedt" text="Sicherungen werden geholt" />
  {:else if !l.bereit}
    <p class="marke-text warn">{l.grund}</p>
  {:else if !l.sicherungen.length}
    <p class="leise">Keine Sicherung {ort}.</p>
  {:else}
    <p class="leise">Neueste zuerst</p>
    <div>
      {#each l.sicherungen as s, k (s.kennung)}
        <Sicherungszeile sicherung={s} neueste={k === 0} gewaehlt={gewaehlt?.quelle === s.quelle && gewaehlt.kennung === s.kennung} onwahl={() => (gewaehlt = s)} />
      {/each}
    </div>
  {/if}
{/snippet}

{#if laeuft || fertig}
  <Schrittrahmen zurueck={laeuft ? "gesperrt" : true} weiter={laeuft ? { gesperrt: true, titel: "Erst nach dem Einspielen" } : {}}>
    {#if auftrag}<Auftragsfeld {auftrag} wort="Abschnitten fertig" teile={TEILZEICHEN.einspielen} onneu={(a) => (auftrag = a)} />{/if}
    {#if fertig}<p class="marke-text gut"><Symbol name="circle-check" />{schritt.text}</p>{:else}<Hinweis />{/if}
  </Schrittrahmen>
{:else}
  <Schrittrahmen weiter={{ text: "Wiederherstellen", symbol: "clock-rotate-left", gesperrt: !gewaehlt, titel: gewaehlt ? undefined : "Erst eine Sicherung wählen", tun: wiederherstellen }}>
    {#if auftrag?.stand === "fehler"}<p class="marke-text schlecht"><Symbol name="triangle-exclamation" />{auftrag.grund || "Das Einspielen ist gescheitert."} Nichts wurde gelöscht.</p>{/if}
    <div class="quellen">
      {#each QUELLEN as [wert, symbol, text, unter] (wert)}
        <button type="button" class="platte" class:offen={quelle === wert} aria-expanded={quelle === wert} onclick={() => (quelle = wert)}>
          <Symbol name={symbol} /><span><b>{text}</b><br /><span class="leise">{unter}</span></span>
        </button>
      {/each}
    </div>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    {#if quelle === "datei"}
      <Sicherungsdatei onfertig={ausDatei} />
      {#if gewaehlt?.quelle === "datei"}<p class="marke-text gut"><Symbol name="circle-check" />{gewaehlt.name} ist da und gewählt.</p>{/if}
    {:else if quelle === "geraet"}
      <Karte titel="Sicherungsordner" symbol="folder-open">{@render sicherungen(listen.geraet, "im Sicherungsordner")}</Karte>
    {:else if wolke}
      <Anschlusskarte anschluss={wolke} ongeaendert={wolkeLaden}>{@render sicherungen(listen.kellerwolke, "in der Kellerwolke")}</Anschlusskarte>
    {:else}
      <Zustand art="laedt" text="Kellerwolke wird gefragt" />
    {/if}
  </Schrittrahmen>
{/if}

<style>
  .offen {
    background: var(--messing-hauch);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--messing) 50%, transparent);
  }
</style>
