<script lang="ts">
  // Hinter dem Schloss, für die Eltern: was sie sehen (auch für das Kind), das Profil verlassen (auf einem fest gestellten Gerät nur mit der Eltern-PIN,
  // POST /api/familie/verlassen) und die Darstellung des Geräts (Hell, Dunkel, System; Schriftgröße), dauerhaft gemerkt.
  import { ladeFamilie, verlasseProfil } from "../../lib/api/familie";
  import { LIZENZ, NENNUNG } from "../../lib/kind/samtpfote";
  import { darstellung, wahlen } from "../../lib/stand/darstellung.svelte";

  let { einblick = [], onverlassen, onschliessen }: { einblick?: string[]; onverlassen: () => void; onschliessen: () => void } = $props();

  /** Was die Eltern sehen, für das Kind gesagt (FAMILIE.md, Einblick: für das Kind sichtbar) */
  const EINBLICK: Record<string, string> = { titel: "die Titel", lesezeit: "die Lesezeit", fortschritt: "wie weit du bist", grober_fortschritt: "ungefähr, wie weit du bist", zuletzt: "wann du zuletzt gelesen hast", geteiltes: "nur, was du teilst" };
  let sehen = $derived.by(() => {
    const teile = einblick.map((e) => EINBLICK[e]).filter(Boolean);
    if (!teile.length) return "";
    const liste = teile.length < 2 ? teile[0] : `${teile.slice(0, -1).join(", ")} und ${teile.at(-1)}`;
    return `Deine Eltern sehen ${liste}.`;
  });

  const LAENGE = 8;
  let gebunden = $state<boolean | null>(null);
  let pin = $state("");
  let falsch = $state(false);
  let fehler = $state("");
  let sendet = $state(false);

  $effect(() => {
    // Weiß das Gerät es nicht, gilt das Strengere
    ladeFamilie().then((f) => (gebunden = !!f.geraet?.gebunden_an)).catch(() => (gebunden = true));
  });

  function tippe(z: string) {
    falsch = false;
    if (pin.length < LAENGE) pin += z;
  }

  async function hinaus() {
    if (gebunden && !pin) return;
    sendet = true;
    fehler = "";
    try {
      await verlasseProfil(gebunden ? pin : undefined);
      onverlassen();
    } catch (e) {
      falsch = true;
      pin = "";
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      sendet = false;
    }
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape") onschliessen();
    else if (gebunden && /^\d$/.test(e.key)) tippe(e.key);
    else if (gebunden && e.key === "Backspace") pin = pin.slice(0, -1);
    else if (e.key === "Enter") void hinaus();
    else return;
    e.preventDefault();
  }
</script>

<svelte:window onkeydown={taste} />

<div class="k-dialog" role="dialog" aria-modal="true" aria-label="Für Eltern">
  <div>
    <div class="k-dialogkopf">
      <i class="fa-solid fa-lock" aria-hidden="true"></i><span>Für Eltern</span>
      <button class="k-schloss" type="button" aria-label="Schließen" onclick={onschliessen}><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>
    </div>

    {#if sehen}<p class="k-einblick"><i class="fa-solid fa-eye" aria-hidden="true"></i>{sehen}</p>{/if}

    {#if gebunden}
      <div class="k-pinstellen" class:falsch aria-label="{pin.length} Ziffern eingegeben">
        {#each { length: Math.max(4, pin.length) } as _, i (i)}<span class:voll={i < pin.length}></span>{/each}
      </div>
      <div class="k-pinfeld">
        {#each ["1", "2", "3", "4", "5", "6", "7", "8", "9"] as z (z)}
          <button class="k-taste" type="button" onclick={() => tippe(z)}>{z}</button>
        {/each}
        <button class="k-taste" type="button" aria-label="Löschen" onclick={() => (pin = pin.slice(0, -1))}><i class="fa-solid fa-delete-left" aria-hidden="true"></i></button>
        <button class="k-taste" type="button" onclick={() => tippe("0")}>0</button>
        <button class="k-taste haupt" type="button" aria-label="Hinaus" disabled={!pin || sendet} onclick={() => void hinaus()}><i class="fa-solid fa-right-from-bracket" aria-hidden="true"></i></button>
      </div>
    {:else if gebunden === false}
      <button class="k-taste quer haupt" type="button" disabled={sendet} onclick={() => void hinaus()}><i class="fa-solid fa-users" aria-hidden="true"></i>Profil wechseln</button>
    {/if}
    {#if fehler}<p class="k-fehler" role="alert">{fehler}</p>{/if}

    <div class="k-dialogzeile">
      <span>Licht</span>
      <div class="k-wahl" role="radiogroup" aria-label="Licht">
        {#each wahlen.thema as [wert, name] (wert)}
          <button class="k-taste" class:an={darstellung.thema === wert} type="button" role="radio" aria-checked={darstellung.thema === wert} onclick={() => (darstellung.thema = wert)}>{name}</button>
        {/each}
      </div>
    </div>
    <div class="k-dialogzeile">
      <span>Schrift</span>
      <div class="k-wahl" role="radiogroup" aria-label="Schriftgröße">
        {#each wahlen.schrift as [wert, name] (wert)}
          <button class="k-taste" class:an={darstellung.schrift === wert} type="button" role="radio" aria-checked={darstellung.schrift === wert} onclick={() => (darstellung.schrift = wert)}>{name}</button>
        {/each}
      </div>
    </div>
    <p class="k-einblick"><i class="fa-solid fa-cat" aria-hidden="true"></i><span>Die Katze ist {NENNUNG}. <a href={LIZENZ} target="_blank" rel="noopener">Nutzungsbedingungen</a></span></p>
  </div>
</div>
