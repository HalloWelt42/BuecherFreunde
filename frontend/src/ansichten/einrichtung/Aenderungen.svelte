<script lang="ts">
  // Ende des wieder geöffneten Assistenten: jede vorgemerkte Änderung mit Haken, darunter, was unverändert bleibt. Übernommen
  // wird nur, was angehakt ist; vorher nennt die Rückfrage jede Änderung. Entfernt wird nichts.
  import { ladeAenderungen, uebernimmAenderungen, type Aenderungen } from "../../lib/api/einrichtung";
  import { aenderungenZahl, uebernehmensfolgen } from "../../lib/einrichtung/saetze";
  import { navigate } from "../../lib/router.svelte";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let liste = $state<Aenderungen | null>(null);
  let aus = $state<Set<string>>(new Set());
  let fehler = $state("");

  async function lade() {
    try {
      liste = await ladeAenderungen();
      fehler = "";
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => void lade());

  let gewaehlt = $derived(liste?.aenderungen.filter((a) => !aus.has(a.id)) ?? []);

  function hake(id: string, an: boolean) {
    const neu = new Set(aus);
    if (an) neu.delete(id);
    else neu.add(id);
    aus = neu;
  }

  async function uebernimm() {
    if (!liste) return;
    const n = gewaehlt.length;
    if (!n) return schliesse();
    const ja = await frage({ titel: `${aenderungenZahl(n)} übernehmen?`, folgen: uebernehmensfolgen(gewaehlt), ja: "Übernehmen", symbol: "check", gefahr: false });
    if (!ja) return;
    const r = await uebernimmAenderungen(liste.stand, gewaehlt.map((a) => a.id));
    melde.gut(`${aenderungenZahl(r.uebernommen.length)} übernommen`);
    await einrichtung.laden();
    navigate("/settings/wartung");
  }

  async function schliesse() {
    const zahl = liste?.aenderungen.length ?? 0;
    const ja = await frage({
      titel: "Ohne Übernehmen schließen?",
      folgen: [zahl ? `${aenderungenZahl(zahl)} ${zahl === 1 ? "fällt" : "fallen"} weg, auch vorgemerkte Schlüssel.` : "Es ist nichts vorgemerkt.", "Geändert wird nichts."],
      ja: "Schließen",
      symbol: "xmark",
      gefahr: false,
    });
    if (!ja) return;
    await einrichtung.schliesse();
    navigate("/settings/wartung");
  }
</script>

<Schrittrahmen weiter={gewaehlt.length ? { text: `Übernehmen (${gewaehlt.length})`, symbol: "check", tun: uebernimm } : { text: "Schließen", symbol: "xmark", gesperrt: !liste, tun: schliesse }}>
  {#if liste}
    <p class="klein">{liste.aenderungen.length ? `${aenderungenZahl(liste.aenderungen.length)}. Übernommen wird nur, was angehakt ist.` : "Keine Änderungen vorgemerkt."}</p>
    {#if liste.aenderungen.length}
      <div class="ew-uebersicht">
        {#each liste.aenderungen as a (a.id)}
          <label class="haekchen ew-aenderung platte">
            <input type="checkbox" checked={!aus.has(a.id)} onchange={(e) => hake(a.id, e.currentTarget.checked)} />
            <span><b>{a.was}</b>{#if a.alt}<br /><span class="leise">bisher {a.alt}</span>{/if}</span>
          </label>
        {/each}
      </div>
    {/if}
    {#if liste.unveraendert.length}
      <section class="ew-uebersicht">
        <h3 class="ew-gruppe-kopf"><Symbol name="equals" />Unverändert <span class="leise zahl">{liste.unveraendert.length}</span></h3>
        <div class="ew-liste">
          {#each liste.unveraendert as name (name)}<div class="stelle zeile-stand zwei"><span class="led gut"></span><span><b>{name}</b></span></div>{/each}
        </div>
      </section>
    {/if}
    <p class="marke-text info"><Symbol name="shield-halved" />Entfernt wird hier nichts.</p>
  {:else if fehler}
    <Zustand art="fehler" text={fehler} onerneut={() => void lade()} />
  {:else}
    <Zustand art="laedt" text="Änderungen werden geholt" />
  {/if}
</Schrittrahmen>
