<script lang="ts">
  // Schritt Verbinden (Umzug): Adresse des alten Geräts und Einmalcode. "Verbinden" holt Sicherung, Einstellungen und Schlüssel
  // direkt und beginnt "Sicherung einspielen"; das alte Gerät bleibt unverändert. Danach gibt es das Konto vom alten Gerät,
  // der Assistent fragt nach der Anmeldung.
  import { onDestroy, onMount } from "svelte";
  import { ApiError } from "../../lib/api/client";
  import { ladeWiederherstellstand, verbindeUmzug, type Auftragsstand, type Schritt, type Umzugsergebnis } from "../../lib/api/einrichtung";
  import { TEILZEICHEN } from "../../lib/einrichtung/ablauf";
  import { laeuftNoch } from "../../lib/einrichtung/saetze";
  import { imTakt } from "../../lib/einrichtung/takt";
  import { anzahl, groesse } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Codefeld from "../../lib/teile/Codefeld.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { CODE_LAENGE, codeNormal } from "../anmeldung/kopplung";
  import Auftragsfeld from "./Auftragsfeld.svelte";
  import Hinweis from "./Hinweis.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  const NAMEN: Record<string, string> = { kellerwolke: "Kellerwolke", leitstelle: "Leitstelle", vertonung: "Vertonung", nachschlag: "Nachschlag" };

  let adresse = $state("");
  let code = $state("");
  let fehler = $state("");
  let verbindet = $state(false);
  let ergebnis = $state<Umzugsergebnis | null>(null);
  let auftrag = $state<Auftragsstand | null>(null);
  let halt: (() => void) | null = null;

  function beobachte() {
    halt?.();
    halt = imTakt(async () => {
      try {
        auftrag = (await ladeWiederherstellstand()).auftrag;
        if (!laeuftNoch(auftrag)) await einrichtung.laden();
        return laeuftNoch(auftrag);
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) await einrichtung.laden();
        return false;
      }
    }, 1500);
  }

  onMount(() => {
    ladeWiederherstellstand().then((s) => {
      if (!s.auftrag.stand) return;
      auftrag = s.auftrag;
      if (laeuftNoch(s.auftrag)) beobachte();
    }).catch(() => {});
  });
  onDestroy(() => halt?.());

  async function verbinde(e: SubmitEvent) {
    e.preventDefault();
    verbindet = true;
    fehler = "";
    try {
      ergebnis = await verbindeUmzug(adresse.trim(), code);
      auftrag = ergebnis.einspielen;
      beobachte();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      verbindet = false;
    }
  }

  const name = (a: string) => {
    try {
      return new URL(a).host;
    } catch {
      return a;
    }
  };

  let laeuft = $derived(laeuftNoch(auftrag));
  let fertig = $derived(schritt.stand === "erledigt");
</script>

<Schrittrahmen zurueck={laeuft ? "gesperrt" : true} weiter={{ gesperrt: !fertig, titel: fertig ? undefined : laeuft ? "Erst nach dem Einspielen" : "Erst mit dem alten Gerät verbinden" }}>
  {#if !auftrag?.stand || auftrag.stand === "fehler"}
    <form class="formular" onsubmit={verbinde}>
      <label class="feld">Adresse des alten Geräts<input class="eingabe" type="url" placeholder="https://buecher.beispiel.lan" autocomplete="off" spellcheck="false" bind:value={adresse} disabled={verbindet} /></label>
      <div class="feld"><span>Einmalcode, steht dort unter Einstellungen, Wartung</span><Codefeld {code} laenge={CODE_LAENGE} name="Einmalcode" normal={codeNormal} onwahl={(c) => (code = c)} /></div>
      <div class="reihe"><Knopf text="Verbinden" symbol="link" art="submit" laeuft={verbindet} gesperrt={!adresse.trim() || code.length !== CODE_LAENGE} /></div>
      {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
      {#if auftrag?.stand === "fehler"}<p class="marke-text schlecht">{auftrag.grund || "Das Einspielen ist gescheitert."} Nichts wurde gelöscht.</p>{/if}
    </form>
  {/if}
  {#if ergebnis}
    <div class="platte karte">
      <p class="marke-text gut"><Symbol name="circle-check" />Verbunden mit {name(adresse)}</p>
      <dl class="angaben">
        <dt>Sicherung</dt><dd class="zahl">{ergebnis.sicherung}</dd>
        <dt>Einstellungen</dt><dd>{ergebnis.einstellungen.map((a) => NAMEN[a] ?? a).join(", ") || "keine Anschlüsse"}{#if ergebnis.schluessel.length}, Schlüssel für {ergebnis.schluessel.map((a) => NAMEN[a] ?? a).join(" und ")}{/if}</dd>
        <dt>Originale</dt><dd class="zahl">{ergebnis.originale.ort === "kellerwolke" ? "in der Kellerwolke" : "auf dem alten Gerät"}, {anzahl(ergebnis.originale.anzahl, "Original", "Originale")}, {groesse(ergebnis.originale.groesse)}</dd>
      </dl>
      <p class="leise">Das alte Gerät bleibt unverändert.</p>
    </div>
  {/if}
  {#if auftrag?.stand && auftrag.stand !== "fehler"}
    <Auftragsfeld {auftrag} wort="Abschnitten fertig" teile={TEILZEICHEN.einspielen} onneu={(a) => (auftrag = a)} />
    {#if laeuft}<Hinweis />{/if}
  {/if}
</Schrittrahmen>
