<script lang="ts">
  import { untrack } from "svelte";
  import { kopple } from "../../lib/api/anmeldung";
  import type { AppAngaben } from "../../lib/api/config";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import { CODE_LAENGE, codeNormal, geraeteart, geraetename } from "./kopplung";

  let { angaben, anfang, onerfolg, onzurueck }: { angaben: AppAngaben; anfang: string; onerfolg: (token: string) => void; onzurueck: () => void } = $props();

  let code = $state(untrack(() => anfang));
  let geraet = $state(geraetename(navigator.userAgent, navigator.maxTouchPoints));
  let fokus = $state(false);
  let fehler = $state("");
  let laeuft = $state(false);
  const stellen = Array.from({ length: CODE_LAENGE }, (_, n) => n);

  async function koppeln(e: SubmitEvent) {
    e.preventDefault();
    fehler = "";
    laeuft = true;
    try {
      onerfolg(await kopple(code, geraet.trim(), geraeteart()));
    } catch (grund) {
      fehler = grund instanceof Error ? grund.message : String(grund);
    } finally {
      laeuft = false;
    }
  }

  function tippt(e: Event & { currentTarget: HTMLInputElement }) {
    code = codeNormal(e.currentTarget.value);
    e.currentTarget.value = code;
  }
</script>

<form class="formular" onsubmit={koppeln}>
  <p class="klein">Den Code aus der Kellerwolke{#if angaben.kellerwolke}{" "}unter <b>{angaben.kellerwolke}</b>{/if} eintippen, dort Einstellungen, Geräte. Danach bleibt dieses Gerät angemeldet, bis du es trennst. Ein Passwort wird hier nicht gespeichert.</p>
  <label class="codefeld" class:fokus>
    <span class="kaestchen" aria-hidden="true">
      {#each stellen as n (n)}<span class="k" class:mitte={n === CODE_LAENGE / 2} class:aktiv={fokus && n === Math.min(code.length, CODE_LAENGE - 1)}>{code[n] ?? ""}</span>{/each}
    </span>
    <input aria-label="Kopplungscode" value={code} autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" oninput={tippt} onfocus={() => (fokus = true)} onblur={() => (fokus = false)} />
  </label>
  <label class="feld">Name des Geräts<input class="eingabe" maxlength="60" bind:value={geraet} /></label>
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
  <Knopf text="Koppeln" symbol="link" art="submit" haupt laeuft={laeuft} gesperrt={code.length !== CODE_LAENGE || !geraet.trim()} />
  <Knopf text="Zurück zur Anmeldung" symbol="chevron-left" gesperrt={laeuft} onclick={onzurueck} />
</form>

<style>
  .codefeld {
    position: relative;
    display: block;
  }
  .kaestchen {
    display: grid;
    grid-template-columns: repeat(8, minmax(0, 1fr));
    gap: 0.25rem;
  }
  .k {
    height: 3rem;
    display: grid;
    place-items: center;
    border-radius: var(--r1);
    font: 600 1.25rem var(--codeschrift);
    background: var(--vertieft);
    box-shadow:
      inset 0 1px 2px rgb(var(--schatten) / 0.16),
      inset 0 0 0 1px var(--linie);
  }
  .k.mitte {
    margin-left: 0.375rem;
  }
  .k.aktiv {
    box-shadow: inset 0 0 0 2px var(--messing);
  }
  .codefeld input {
    position: absolute;
    inset: 0;
    width: 100%;
    border: 0;
    background: none;
    color: transparent;
    caret-color: transparent;
    outline: 0;
    font-size: 1rem;
  }
</style>
