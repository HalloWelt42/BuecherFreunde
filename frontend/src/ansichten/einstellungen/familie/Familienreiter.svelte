<script lang="ts">
  // Elternbereich (BF-78, Entwurf kinder-1 Abschnitt 5): die Profile der Familie, das gewählte steht rechts. Welches gewählt
  // ist, steht in der Adresse (/settings/familie/<id>), so führt das Zuordnen der Freigaben genau hierher zurück.
  import { navigate, route } from "../../../lib/router.svelte";
  import { familie } from "../../../lib/stand/familie.svelte";
  import { ich } from "../../../lib/stand/ich.svelte";
  import { melde } from "../../../lib/stand/meldungen.svelte";
  import { profilformular } from "../../../lib/stand/profilformular.svelte";
  import Zustand from "../../../lib/teile/Zustand.svelte";
  import Profilansicht from "./Profilansicht.svelte";
  import Profilliste from "./Profilliste.svelte";

  let gefragt = $derived(route.path.split("/")[3] ?? "");
  /** Ohne Angabe das erste Kind (dafür ist der Bereich da), sonst das eigene Profil */
  let gewaehlt = $derived(familie.profil(gefragt) ?? familie.profile.find((p) => p.rolle === "kind") ?? ich.profil ?? familie.profile[0] ?? null);

  $effect(() => {
    void familie.ladeStufen().catch((e) => melde.schlecht(e, "Stufen nicht geladen"));
    void familie.laden().catch(() => undefined);
  });

  function neu() {
    profilformular.oeffne({ neu: "kind" }, (p) => navigate(`/settings/familie/${p.id}`, true));
  }
</script>

<div class="eltern">
  <Profilliste gewaehlt={gewaehlt?.id ?? ""} onneu={ich.darf("profile") ? neu : undefined} />
  {#if gewaehlt}
    {#key gewaehlt.id}<Profilansicht profil={gewaehlt} />{/key}
  {:else}
    <Zustand text="Noch kein Profil." />
  {/if}
</div>
