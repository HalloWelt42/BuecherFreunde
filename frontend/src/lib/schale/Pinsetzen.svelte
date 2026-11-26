<script lang="ts">
  // PIN eines Profils setzen, ändern oder entfernen (BF-78): Erwachsene eine PIN aus Ziffern, zweimal eingegeben; Kinder eine
  // Bild-PIN aus drei Bildern. Entfernen erst nach der Rückfrage, denn danach öffnet jeder das Profil.
  import { setzePin, type Profil } from "../api/familie";
  import { bildName, pinGueltig } from "../familie";
  import { familie } from "../stand/familie.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { frage } from "../stand/rueckfrage.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Bildpinfeld from "../teile/Bildpinfeld.svelte";

  let { profil, ongeaendert }: { profil: Profil; ongeaendert: (p: Profil) => void } = $props();

  let kind = $derived(profil.rolle === "kind");
  let gesetzt = $derived(kind ? profil.hat_bild_pin : profil.hat_pin);
  let art = $derived(kind ? "Bild-PIN" : "PIN");
  let pin = $state("");
  let nochmal = $state("");
  let bilder = $state<string[]>([]);
  let laeuft = $state(false);
  let feld: { leere: () => void } | undefined = $state();

  let bereit = $derived(kind ? bilder.length > 0 : pinGueltig(pin, familie.zugang) && pin === nochmal);
  let hinweis = $derived(!kind && pin && nochmal && pin !== nochmal ? "Die beiden Eingaben stimmen nicht überein." : "");

  async function tun(wert: Parameters<typeof setzePin>[1], gut: string) {
    laeuft = true;
    try {
      ongeaendert(await setzePin(profil.id, wert));
      melde.gut(gut);
      pin = "";
      nochmal = "";
      bilder = [];
      feld?.leere();
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
    } finally {
      laeuft = false;
    }
  }

  function speichere(e: SubmitEvent) {
    e.preventDefault();
    if (bereit) void tun(kind ? { bild_pin: bilder } : { pin }, `${art} gespeichert`);
  }

  async function entferne() {
    const ja = await frage({
      titel: `${art} von ${profil.name} entfernen?`,
      folgen: [`Danach öffnet jeder auf jedem Gerät das Profil ${profil.name} mit einem Tipp.`, "Lesestand, Notizen und alles andere bleiben."],
      ja: `${art} entfernen`,
      symbol: "lock-open",
    });
    if (ja) await tun({ entfernen: true }, `${art} entfernt`);
  }
</script>

<form class="pinsetzen" onsubmit={speichere}>
  <p class="leise">{gesetzt ? `${art} gesetzt. Eine neue ersetzt sie.` : `Noch keine ${art}.`}</p>
  {#if kind}
    <div class="bildpinklein">
      <Bildpinfeld bind:this={feld} zugang={familie.zugang} name="Neue Bild-PIN" gesperrt={laeuft} onvoll={(b) => (bilder = b)} />
    </div>
    {#if bilder.length}<p class="leise">Neu: {bilder.map(bildName).join(", ")}</p>{/if}
  {:else}
    <div class="zwei">
      <label class="feld">Neue PIN, {familie.zugang.pin_stellen_von} bis {familie.zugang.pin_stellen_bis} Ziffern<input class="eingabe" type="password" inputmode="numeric" autocomplete="new-password" maxlength={familie.zugang.pin_stellen_bis} bind:value={pin} disabled={laeuft} /></label>
      <label class="feld">PIN wiederholen<input class="eingabe" type="password" inputmode="numeric" autocomplete="new-password" maxlength={familie.zugang.pin_stellen_bis} bind:value={nochmal} disabled={laeuft} /></label>
    </div>
    {#if hinweis}<p class="marke-text warn" role="alert">{hinweis}</p>{/if}
  {/if}
  <div class="tasten">
    <Knopf text="{art} speichern" symbol="lock" art="submit" {laeuft} gesperrt={!bereit} />
    <Knopf text="{art} entfernen" symbol="lock-open" gesperrt={!gesetzt || laeuft} onclick={() => void entferne()} />
  </div>
</form>

<style>
  .pinsetzen {
    display: grid;
    gap: 0.625rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .bildpinklein {
    --pin-taste: 3rem;
    --pin-abstand: 0.625rem;
    justify-self: start;
  }
  .zwei,
  .tasten {
    display: grid;
    gap: 0.5rem;
    grid-template-columns: repeat(auto-fit, minmax(min(11rem, 100%), 1fr));
  }
</style>
