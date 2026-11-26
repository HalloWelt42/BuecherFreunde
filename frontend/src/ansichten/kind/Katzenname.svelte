<script lang="ts">
  // Das Kind gibt seiner Katze einen Namen (PATCH /api/familie/ich/katze über den Stand ich, je Profil gespeichert). Ab Erstes Lesen tippt es ihn
  // selbst; wer noch nicht liest (Stufe mit Vorlesen von selbst), wählt aus Vorschlägen, die vorgelesen werden.
  import { KATZENNAMEN } from "../../lib/kind/ich";
  import Katze from "../../lib/kind/Katze.svelte";
  import type { Ich } from "../../lib/kind/typen";
  import { ich as ichstand } from "../../lib/stand/ich.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Wer from "./Wer.svelte";

  let { ich, onzurueck }: { ich: Ich; onzurueck: () => void } = $props();

  const HOECHSTENS = 24;
  // svelte-ignore state_referenced_locally
  let name = $state(ich.katze.name);
  let fehler = $state("");
  let sendet = $state(false);
  /** Im Vorlesealter wählt das Kind aus vorgelesenen Vorschlägen, sonst tippt es selbst */
  let selbst = $derived(ich.profil.stufe !== "vorlesen");
  let vorschlaege = $derived([...new Set([...(ich.katze.name ? [ich.katze.name] : []), ...KATZENNAMEN])]);

  function sprich(text: string) {
    vorlesen.entsperre();
    vorlesen.lies(text, "Katzenname");
  }

  function waehle(vorschlag: string) {
    name = vorschlag;
    if (vorlesen.stimmen.length) sprich(vorschlag);
  }

  async function fertig() {
    const neu = name.trim().slice(0, HOECHSTENS);
    if (!neu) return;
    sendet = true;
    fehler = "";
    try {
      await ichstand.katzenname(neu);
      onzurueck();
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      sendet = false;
    }
  }

  $effect(() => vorlesen.pruefe());
</script>

<header class="k-kopf">
  <Wer profil={ich.profil} />
  <div class="k-rechts">
    <button class="k-taste rund" type="button" aria-label="Zum Regal" onclick={onzurueck}><i class="fa-solid fa-house" aria-hidden="true"></i></button>
  </div>
</header>

<div class="k-mitte">
  <div class="k-namensfeld">
    <Katze name={name.trim() || ich.katze.name} schnurren={ich.katze.schnurren} groesse="clamp(7rem, 14vw, 10rem)" />
    {#if selbst}
      <input bind:value={name} maxlength={HOECHSTENS} aria-label="Name der Katze" placeholder="Name" autocomplete="off" enterkeyhint="done" onkeydown={(e) => e.key === "Enter" && void fertig()} />
    {:else}
      <div class="k-vorschlaege" role="radiogroup" aria-label="Namen für die Katze">
        {#each vorschlaege as v (v)}
          <button class="k-taste quer" class:an={name === v} type="button" role="radio" aria-checked={name === v} onclick={() => waehle(v)}>
            {#if vorlesen.stimmen.length}<i class="fa-solid fa-volume-high" aria-hidden="true"></i>{/if}{v}
          </button>
        {/each}
      </div>
    {/if}
    <button class="k-taste quer haupt" type="button" disabled={!name.trim() || sendet} onclick={() => void fertig()}><i class="fa-solid fa-check" aria-hidden="true"></i>Fertig</button>
    {#if fehler}<p class="k-fehler">{fehler}</p>{/if}
  </div>
</div>

<div class="k-fuss"></div>
