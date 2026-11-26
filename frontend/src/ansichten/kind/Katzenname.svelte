<script lang="ts">
  // Das Kind gibt seiner Katze einen Namen (PATCH /api/familie/ich/katze über den Stand ich, je Profil gespeichert). Ab Erstes Lesen tippt es ihn
  // selbst; im Vorlesealter wählt es aus Vorschlägen, die beim Antippen vorgesprochen werden (lib/kind/ansage.svelte.ts).
  import { untrack } from "svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import { ladeStufen } from "../../lib/api/familie";
  import { KATZENNAMEN } from "../../lib/kind/ich";
  import Katze from "../../lib/kind/Katze.svelte";
  import type { Ich } from "../../lib/kind/typen";
  import { ich as ichstand } from "../../lib/stand/ich.svelte";
  import Wer from "./Wer.svelte";

  let { ich, onzurueck }: { ich: Ich; onzurueck: () => void } = $props();

  /** Wie stufen.json (katze.name_hoechstens) */
  const HOECHSTENS = 30;
  // svelte-ignore state_referenced_locally
  let name = $state(ich.katze.name);
  let fehler = $state("");
  let sendet = $state(false);
  /** Im Vorlesealter wählt das Kind aus vorgesprochenen Vorschlägen, sonst tippt es selbst; das sagt der Server je Stufe */
  let selbst = $derived(ich.katze.name_eingabe === "tippen");
  // Die Vorschläge kommen aus stufen.json (GET /api/familie/stufen), bis dahin die eigenen
  let vomServer = $state<string[]>([]);
  $effect(() => {
    if (selbst) return;
    ladeStufen()
      .then((s) => {
        const liste = (s as { katze_vorschlaege?: unknown }).katze_vorschlaege;
        if (Array.isArray(liste)) vomServer = liste.filter((n): n is string => typeof n === "string");
      })
      .catch(() => undefined);
  });
  let vorschlaege = $derived([...new Set([...(ich.katze.name ? [ich.katze.name] : []), ...(vomServer.length ? vomServer : KATZENNAMEN)])]);

  function waehle(vorschlag: string) {
    name = vorschlag;
    // Der Name wird vorgesprochen, damit auch wer noch nicht liest weiß, was er wählt
    void ansage.taste(vorschlag);
  }

  $effect(() => untrack(() => void ansage.hinweis(selbst ? "Wie soll deine Katze heißen? Tippe den Namen ein." : "Wie soll deine Katze heißen? Tippe einen Namen an.")));

  async function fertig() {
    const neu = name.trim().slice(0, HOECHSTENS);
    if (!neu) return;
    sendet = true;
    fehler = "";
    try {
      await ichstand.katzenname(neu);
      onzurueck();
      void ansage.hinweis(`Deine Katze heißt jetzt ${neu}.`);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      sendet = false;
    }
  }

</script>

<header class="k-kopf">
  <Wer profil={ich.profil} />
  <div class="k-rechts">
    <button class="k-taste rund" type="button" aria-label="Zum Regal" onclick={() => (onzurueck(), void ansage.taste("Zum Regal"))}><i class="fa-solid fa-house" aria-hidden="true"></i></button>
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
            {#if ansage.tasten}<i class="fa-solid fa-volume-high" aria-hidden="true"></i>{/if}{v}
          </button>
        {/each}
      </div>
    {/if}
    <button class="k-taste quer haupt" type="button" disabled={!name.trim() || sendet} onclick={() => void fertig()}><i class="fa-solid fa-check" aria-hidden="true"></i>Fertig</button>
    {#if fehler}<p class="k-fehler">{fehler}</p>{/if}
  </div>
</div>

<div class="k-fuss"></div>
