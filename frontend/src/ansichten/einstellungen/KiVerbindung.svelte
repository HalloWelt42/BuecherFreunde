<script lang="ts">
  import { kiEinstellungen, kiStatus, speichereKi, sucheKiImNetz, type KiEinstellungen, type KiStatus, type KiTreffer } from "../../lib/api/ai";
  import { anzahl } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Auswahl from "../../lib/teile/Auswahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { kiAdresse } from "./kiadresse";

  let einstellungen = $state<KiEinstellungen | null>(null);
  let status = $state<KiStatus | null>(null);
  let fehler = $state("");
  let adresse = $state("");
  let arbeit = $state<"" | "speichern" | "testen" | "suchen" | "modell">("");
  let treffer = $state<KiTreffer[] | null>(null);

  let modelle = $derived<[string, string][]>((status?.modelle ?? []).map((m) => [m, m]));
  let wort = $derived(!status ? "nicht geprüft" : status.erreichbar ? "antwortet" : status.aktiviert === false ? "ausgeschaltet" : "antwortet nicht");
  let led = $derived(!status || status.aktiviert === false ? "aus" : status.erreichbar ? "gut" : "schlecht");

  async function lade() {
    fehler = "";
    try {
      einstellungen = await kiEinstellungen();
      adresse = einstellungen.url;
      status = await kiStatus().catch(() => null);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }
  $effect(() => void lade());

  async function teste() {
    arbeit = "testen";
    status = await kiStatus().catch(() => null);
    arbeit = "";
    if (status?.erreichbar) melde.gut("Die KI antwortet");
    else if (status?.aktiviert === false) melde.info("Die KI ist in der Einrichtung des Servers ausgeschaltet");
    else melde.warn(`Die KI antwortet nicht${status?.grund ? `: ${status.grund}` : ""}`);
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    arbeit = "speichern";
    try {
      einstellungen = await speichereKi({ lm_studio_url: kiAdresse(adresse) });
      adresse = einstellungen.url;
      melde.gut("Adresse gespeichert");
      await teste();
    } catch (err) {
      melde.schlecht(err, "Nicht gespeichert");
    }
    arbeit = "";
  }

  async function suche() {
    arbeit = "suchen";
    treffer = null;
    try {
      treffer = (await sucheKiImNetz()).gefunden ?? [];
    } catch (e) {
      melde.schlecht(e, "Suche gescheitert");
    }
    arbeit = "";
  }

  async function waehleModell(modell: string) {
    arbeit = "modell";
    try {
      einstellungen = await speichereKi({ lm_studio_model: modell });
      melde.gut(`Modell ${modell} gewählt`);
    } catch (e) {
      melde.schlecht(e, "Nicht gewechselt");
    }
    arbeit = "";
  }

  function uebernimm(t: KiTreffer) {
    adresse = kiAdresse(t.url);
    treffer = null;
  }
</script>

{#if fehler}
  <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
{:else if !einstellungen}
  <Zustand art="laedt" text="Wird geladen" />
{:else}
  <dl class="angaben">
    <dt>Stand</dt><dd><span class="lampe"><span class="led {led}"></span>{wort}</span></dd>
    <dt>Eingeschaltet</dt><dd>{einstellungen.aktiviert ? "ja" : "nein, in der Einrichtung des Servers"}</dd>
    {#if !modelle.length}<dt>Modell</dt><dd>{einstellungen.modell}</dd>{/if}
  </dl>
  <form class="reihe schluessel" onsubmit={speichere}>
    <input class="eingabe" type="text" inputmode="url" aria-label="Adresse der KI" placeholder="http://rechner.lan:1234/v1" spellcheck="false" bind:value={adresse} />
    <Knopf text="Speichern" symbol="check" art="submit" laeuft={arbeit === "speichern"} gesperrt={!adresse.trim()} />
  </form>
  {#if modelle.length}
    <div class="feld">Modell<Auswahl name="Modell" werte={modelle.some(([m]) => m === einstellungen?.modell) ? modelle : [[einstellungen.modell, einstellungen.modell], ...modelle]} wert={einstellungen.modell} gesperrt={arbeit === "modell"} onwahl={(m) => void waehleModell(m)} /></div>
  {/if}
  <div class="reihe">
    <Knopf text="Testen" symbol="stethoscope" klein laeuft={arbeit === "testen"} onclick={() => void teste()} />
    <Knopf text="Netz absuchen" symbol="magnifying-glass" klein laeuft={arbeit === "suchen"} onclick={() => void suche()} />
  </div>
  {#if treffer}
    {#each treffer as t (t.url)}
      <div class="stelle zeile-stand eins-knopf"><span><code class="pfad">{t.url}</code><br /><span class="leise zahl">{anzahl(t.modelle, "Modell", "Modelle")}</span></span><Knopf text="Übernehmen" symbol="check" klein onclick={() => uebernimm(t)} /></div>
    {:else}<p class="leise">Im Netz antwortet gerade keine KI.</p>{/each}
  {/if}
  <p class="leise">Ordnet Bücher in Regale ein. Die KI läuft auf einem eigenen Rechner im Haus; Adresse eintragen oder das Netz absuchen und danach speichern.</p>
{/if}
