<script lang="ts">
  // Die Profile der Familie mit Rolle und Stufe, bei Kindern dazu die Gestaltung (BF-88); ein Tipp zeigt das Profil rechts,
  // "Profil" legt ein neues an. Darunter die Stimme der Familie (Entwurf kinder-6).
  import type { Profil } from "../../../lib/api/familie";
  import { einstellungenVon, gestaltungText, rollenText } from "../../../lib/familie";
  import { familie } from "../../../lib/stand/familie.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Profilbild from "../../../lib/teile/Profilbild.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Familienstimme from "./Familienstimme.svelte";

  let { gewaehlt, onneu = undefined }: { gewaehlt: string; onneu?: () => void } = $props();

  /** "Kind, Schule, Groß" */
  const zeile = (p: Profil) =>
    [rollenText(p, familie.stufen.stufen), p.rolle === "kind" ? gestaltungText(einstellungenVon(p, familie.stufen.stufen).gestaltung) : ""].filter(Boolean).join(", ");
</script>

<nav class="profilliste platte" aria-label="Profile der Familie">
  <div class="kopfzeile">Familie</div>
  {#each familie.profile as p (p.id)}
    <a class="profilzeile" href="/settings/familie/{p.id}" aria-current={p.id === gewaehlt ? "page" : undefined}>
      <Profilbild profil={p} groesse="2.25rem" />
      <span>{p.name}<small>{zeile(p)}</small></span>
      <Symbol name="chevron-right" />
    </a>
  {/each}
  {#if onneu}<Knopf text="Profil" symbol="plus" klein titel="Neues Profil" onclick={onneu} />{/if}
  <Familienstimme />
</nav>
