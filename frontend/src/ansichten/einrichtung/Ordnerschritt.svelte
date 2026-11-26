<script lang="ts">
  // Schritt Ordner der Bücher (Ablage in der Kellerwolke übernehmen): Kellerwolke mit Adresse und App-Zugang, dann den Ordner
  // wählen und prüfen. Gelesen wird nur, in der Kellerwolke ändert sich nichts. "Neu aufbauen" beginnt den Auftrag.
  import { beginneNeuaufbau, ladeAnschluesse, pruefeOrdner, type Anschluss, type Ordnerpruefung, type Schritt } from "../../lib/api/einrichtung";
  import { groesse, zahl } from "../../lib/format";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Anschlusskarte from "./Anschlusskarte.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  let wolke = $state<Anschluss | null>(null);
  let pfad = $state("Bücher");
  let pruefung = $state<Ordnerpruefung | null>(null);
  let prueft = $state(false);
  let fehler = $state("");

  async function wolkeLaden() {
    wolke = (await ladeAnschluesse()).find((a) => a.art === "kellerwolke") ?? null;
  }

  $effect(() => void wolkeLaden().catch((e) => (fehler = e instanceof Error ? e.message : String(e))));

  async function pruefe(e?: SubmitEvent) {
    e?.preventDefault();
    prueft = true;
    fehler = "";
    try {
      pruefung = await pruefeOrdner(pfad.trim());
      await einrichtung.laden();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
      pruefung = null;
    } finally {
      prueft = false;
    }
  }

  async function aufbauen() {
    await beginneNeuaufbau();
    await einrichtung.laden();
    einrichtung.zeige("neuaufbau");
  }

  let bereit = $derived(!!pruefung || schritt.stand === "erledigt");
</script>

<Schrittrahmen weiter={{ text: "Neu aufbauen", symbol: "arrows-rotate", gesperrt: !bereit, titel: bereit ? undefined : "Erst den Ordner prüfen", tun: aufbauen }}>
  {#if wolke}
    <Anschlusskarte anschluss={wolke} ongeaendert={wolkeLaden} />
  {:else if !fehler}
    <Zustand art="laedt" text="Kellerwolke wird gefragt" />
  {/if}
  <Karte titel="Ordner der Bücher" symbol="folder-tree">
    <form class="reihe ew-ordnerzeile" onsubmit={pruefe}>
      <input class="eingabe" aria-label="Ordner der Bücher, unter dem Ordner der App" spellcheck="false" bind:value={pfad} />
      <Knopf text="Ordner prüfen" symbol="magnifying-glass" art="submit" laeuft={prueft} gesperrt={!pfad.trim()} />
    </form>
    <p class="leise">Unter dem Ordner der App in der Kellerwolke, Vorgabe Bücher.</p>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    {#if pruefung}
      <dl class="angaben">
        <dt>Bücher</dt><dd class="zahl">{zahl(pruefung.buecher)}{#if pruefung.groesse}, {groesse(pruefung.groesse)}{/if}</dd>
        <dt>mit Auszug</dt><dd class="zahl">{zahl(pruefung.mit_auszug)}</dd>
        <dt>ohne Auszug</dt><dd class="zahl">{zahl(pruefung.ohne_auszug)}</dd>
        {#if pruefung.mit_persoenlichem}<dt>mit Persönlichem</dt><dd class="zahl">{zahl(pruefung.mit_persoenlichem)}</dd>{/if}
        {#if pruefung.schon_da}<dt>schon da</dt><dd class="zahl">{zahl(pruefung.schon_da)}</dd>{/if}
        <dt>Profile</dt>
        <dd>
          {#if pruefung.profile.length}
            <span class="ew-profilchips">{#each pruefung.profile as name, k (k)}<span class="chip"><Symbol name="user" />{name}</span>{/each}</span>
          {:else}
            <span class="leise">{pruefung.profile_datei ? "keine in der Datei der Profile" : "ohne Datei der Profile"}</span>
          {/if}
        </dd>
      </dl>
    {/if}
    <p class="leise ew-hinweiszeile"><Symbol name="lock" /><span>Gelesen wird nur, in der Kellerwolke ändert sich nichts. Die Profile entstehen ohne PIN, die setzt du danach neu.</span></p>
  </Karte>
</Schrittrahmen>
