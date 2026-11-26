<script lang="ts">
  // Umzug auf ein neues Gerät (BF-82), hier das alte Gerät: "Umzug vorbereiten" legt eine frische Sicherung an und zeigt
  // Adresse und Einmalcode in Kästchen wie beim Koppeln. Der Code steht nur einmal da; danach ist nur noch zu sehen, ob er
  // eingelöst ist. Dieses Gerät bleibt unverändert, bis man es selbst abschaltet.
  import { beendeUmzug, bereiteUmzugVor, ladeUmzug, type Umzugsstand, type UmzugVorbereitet } from "../../lib/api/einrichtung";
  import { umzugGilt } from "../../lib/einrichtung/saetze";
  import { datumZeit } from "../../lib/format";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Codekaestchen from "../../lib/teile/Codekaestchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Lampe from "../../lib/teile/Lampe.svelte";
  import { CODE_LAENGE, codeNormal } from "../anmeldung/kopplung";
  import { vorgaenge } from "./vorgaenge.svelte";

  let stand = $state<Umzugsstand | null>(null);
  /** Nur gleich nach dem Vorbereiten bekannt */
  let neu = $state<UmzugVorbereitet | null>(null);
  let laeuft = $state(false);

  async function lade() {
    try {
      stand = await ladeUmzug();
    } catch {
      stand = null;
    }
  }

  $effect(() => void lade());

  async function tu(arbeit: () => Promise<void>, fehlertext: string) {
    laeuft = true;
    try {
      await arbeit();
    } catch (e) {
      melde.schlecht(e, fehlertext);
    } finally {
      laeuft = false;
    }
  }

  async function vorbereiten() {
    neu = await bereiteUmzugVor();
    await lade();
    void vorgaenge.ladeSicherungen();
  }

  async function beenden() {
    if (stand?.eingeloest_am) {
      const ja = await frage({
        titel: "Umzug beenden?",
        folgen: ["Das neue Gerät holt danach nichts mehr von hier, auch keine Originale.", "Bestand und Sicherung bleiben hier, wie sie sind."],
        ja: "Umzug beenden",
        symbol: "ban",
        gefahr: false,
      });
      if (!ja) return;
    }
    stand = await beendeUmzug();
    neu = null;
  }

  async function kopiere() {
    if (!neu) return;
    await navigator.clipboard.writeText(neu.code);
    melde.gut("Code kopiert");
  }

  let wartet = $derived(!!stand?.vorbereitet && !stand.eingeloest_am && !stand.gesperrt);
</script>

{#if stand?.gesperrt}
  <p class="marke-text schlecht">Zu viele falsche Codes; dieser Umzug gilt nicht mehr.</p>
{/if}
{#if neu && wartet}
  <p class="klein">Frische Sicherung angelegt. Auf dem neuen Gerät im Assistenten "Umzug" eintragen:</p>
  <dl class="angaben"><dt>Adresse</dt><dd><code class="pfad">{location.origin}</code></dd><dt>Gültig</dt><dd>{umzugGilt(neu.gilt_bis)}</dd></dl>
  <Codekaestchen code={codeNormal(neu.code)} laenge={CODE_LAENGE} anzeige />
  <Lampe stand="warn" text="wartet auf das neue Gerät" />
  <div class="ew-tasten2">
    <Knopf text="Code kopieren" symbol="copy" klein onclick={() => void kopiere()} />
    <Knopf text="Code beenden" symbol="ban" klein laeuft={laeuft} onclick={() => void tu(beenden, "Nicht beendet")} />
  </div>
  <p class="leise">Dieses Gerät bleibt unverändert, bis du es selbst abschaltest.</p>
{:else if stand?.eingeloest_am}
  <Lampe stand="gut" text="Eingelöst am {datumZeit(stand.eingeloest_am)}" />
  {#if stand.sitzung_bis}<p class="leise">Das neue Gerät holt Sicherung und Originale bis {datumZeit(stand.sitzung_bis)}. Dieses Gerät bleibt unverändert.</p>{/if}
  <div class="ew-tasten2">
    <Knopf text="Neu vorbereiten" symbol="truck-ramp-box" klein laeuft={laeuft} onclick={() => void tu(vorbereiten, "Nicht vorbereitet")} />
    <Knopf text="Umzug beenden" symbol="ban" klein gesperrt={laeuft} onclick={() => void tu(beenden, "Nicht beendet")} />
  </div>
{:else if wartet}
  <p class="klein">Ein Code gilt {umzugGilt(stand?.gilt_bis ?? null)}. Er stand nur einmal da; für einen neuen Code neu vorbereiten.</p>
  <Lampe stand="warn" text="wartet auf das neue Gerät" />
  <div class="ew-tasten2">
    <Knopf text="Neu vorbereiten" symbol="truck-ramp-box" klein laeuft={laeuft} onclick={() => void tu(vorbereiten, "Nicht vorbereitet")} />
    <Knopf text="Code beenden" symbol="ban" klein gesperrt={laeuft} onclick={() => void tu(beenden, "Nicht beendet")} />
  </div>
{:else}
  <p class="klein">Legt eine frische Sicherung an und zeigt einen Einmalcode. Damit holt ein neues Gerät Sicherung, Einstellungen und Schlüssel direkt von hier.</p>
  <div class="reihe"><Knopf text="Umzug vorbereiten" symbol="truck-ramp-box" klein laeuft={laeuft} onclick={() => void tu(vorbereiten, "Nicht vorbereitet")} /></div>
  <p class="leise">Dieses Gerät bleibt unverändert, bis du es selbst abschaltest.</p>
{/if}
