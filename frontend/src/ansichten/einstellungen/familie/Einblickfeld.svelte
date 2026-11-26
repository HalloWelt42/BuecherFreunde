<script lang="ts">
  // Was die Eltern vom Lesen des Kindes sehen, abgestuft nach Stufe; der Hinweis darunter sagt, dass das Kind es ebenso sieht
  import { ladeEinblick, type Einblick, type Profil } from "../../../lib/api/familie";
  import { einblickHinweis, einblickZeile } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";

  let { profil }: { profil: Profil } = $props();

  let einblick = $state<Einblick | null>(null);
  let fehler = $state("");
  let hinweis = $derived(einblick ? einblickHinweis(profil.name, einblick.sichtbar, profil.stufe, familie.stufen.stufen) : "");

  $effect(() => {
    void profil.stufe;
    ladeEinblick(profil.id).then((e) => ((einblick = e), (fehler = ""))).catch((e) => (fehler = e instanceof Error ? e.message : String(e)));
  });
</script>

<section class="elternfeld platte">
  <h3><Symbol name="eye" />Was du siehst</h3>
  {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>
  {:else if !einblick}<p class="leise">Wird geladen</p>
  {:else}
    <div class="einblick">
      {#each einblick.eintraege as e (e.buch.id)}
        <div class="elternzeile"><span>{e.buch.title}<small>{einblickZeile(e)}</small></span><Symbol name={e.fortschritt >= 1 ? "circle-check" : "book-open"} /></div>
      {:else}<p class="leise">{profil.name} hat noch nichts gelesen.</p>{/each}
    </div>
    <span class="hinweis"><Symbol name="circle-info" /> {hinweis}</span>
  {/if}
</section>
