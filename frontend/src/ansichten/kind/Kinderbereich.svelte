<script lang="ts">
  // Kinderbereich (BF-78, docs/neubau/FAMILIE.md): der kindgerechte, aufs Lesen reduzierte Zugang. Wird eingebunden, wenn das
  // aktive Profil ein Kind ist (lib/kind/ich.ts, nutztKinderbereich). Keine Seitenleiste, kein Kopf der Erwachsenen, keine
  // Werkzeugzeilen: Regal, Lesen, Ruhe und die Katze. Was das Kind darf, sagt der Server über GET /api/familie/ich; die Wahrheit
  // darüber hält der Stand lib/stand/ich.svelte.ts, hier wird sie nur kindgerecht gelesen.
  //
  // ich: die Antwort von GET /api/familie/ich (der Stand ich.jetzt); ohne Angabe gilt der Stand selbst.
  // onverlassen: das Kind hat das Profil verlassen (Schloss mit Eltern-PIN); ohne Angabe lädt die Seite neu.
  import "@fortawesome/fontawesome-free/css/regular.css";
  import "../../stil/kind.css";
  import { untrack } from "svelte";
  import { matchRoute, navigate, route } from "../../lib/router.svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import { meldeLesezeit } from "../../lib/kind/api";
  import { ichAus } from "../../lib/kind/ich";
  import { Lesezeituhr } from "../../lib/kind/lesezeit.svelte";
  import type { Ich, Kinderdarstellung } from "../../lib/kind/typen";
  import { nutzeSchrift } from "../../lib/leser/schriften";
  import { anschluesse } from "../../lib/stand/anschluesse.svelte";
  import { ich as ichstand } from "../../lib/stand/ich.svelte";
  import Elterndialog from "./Elterndialog.svelte";
  import Katzenname from "./Katzenname.svelte";
  import Kinderleser from "./Kinderleser.svelte";
  import Regal from "./Regal.svelte";
  import Ruhe from "./Ruhe.svelte";

  let { ich: vorab = null, onverlassen }: { ich?: unknown; onverlassen?: () => void } = $props();

  /** So oft fragt der Bereich nach, was gilt (Ruhezeit beginnt, die Eltern ändern etwas) */
  const NACHFRAGE_MS = 60_000;
  const KINDERSCHRIFT = '"Andika", system-ui, sans-serif';

  let fehler = $state("");
  let eltern = $state(false);

  // Bleibt die Darstellung gleich, bleibt sie dasselbe Objekt: der Leser bricht nur um, wenn sich wirklich etwas ändert
  let letzteDarstellung: Kinderdarstellung | null = null;
  let ich = $derived.by<Ich | null>(() => {
    const roh = vorab ?? ichstand.jetzt;
    if (!roh) return null;
    const neu = ichAus(roh);
    if (letzteDarstellung && JSON.stringify(letzteDarstellung) === JSON.stringify(neu.darstellung)) neu.darstellung = letzteDarstellung;
    else letzteDarstellung = neu.darstellung;
    return neu;
  });

  const uhr = new Lesezeituhr({ melde: meldeLesezeit, jetzt: () => Date.now(), sichtbar: () => document.visibilityState === "visible" });

  // Was der Server über die Lesezeit sagt, gilt
  $effect(() => {
    const stand = ich?.lesezeit;
    if (stand) untrack(() => uhr.uebernimm(stand));
  });

  /** Wo das Kind ist; die Adresse ist die Wahrheit, so geht auch das Zurück des Geräts */
  let ort = $derived.by(() => {
    const lesen = matchRoute("/book/:id/read", route.path);
    if (lesen && Number(lesen.id) > 0) return { art: "lesen" as const, buch: Number(lesen.id) };
    if (route.path === "/katze") return { art: "katze" as const, buch: 0 };
    return { art: "regal" as const, buch: 0 };
  });
  let ruht = $derived(uhr.faellig && ort.art !== "lesen");

  async function frage(): Promise<void> {
    try {
      await ichstand.laden();
      fehler = "";
    } catch (e) {
      if (!ich) fehler = e instanceof Error ? e.message : String(e);
    }
  }

  $effect(() => {
    untrack(() => {
      if (!ich) void frage();
      if (!anschluesse.geladen) void anschluesse.laden();
      nutzeSchrift(KINDERSCHRIFT);
    });
    const uhrAus = uhr.starte();
    const nachfrage = setInterval(() => void frage(), NACHFRAGE_MS);
    return () => {
      uhrAus();
      clearInterval(nachfrage);
    };
  });

  $effect(() => {
    if (ich) nutzeSchrift(ich.darstellung.schrift);
  });

  // Ansagen, wie die Eltern sie für dieses Kind eingestellt haben
  $effect(() => {
    if (ich) ansage.stelle(ich.darstellung.hinweise_sprechen, ich.darstellung.tasten_ansagen);
  });
  // Die Töne der Ansagen dieses Kindes; neu, wenn ein anderes Kind liest
  $effect(() => {
    if (!ich?.profil.id) return;
    untrack(() => void ansage.lade());
    return () => ansage.beende();
  });

  // Jede Bedienung zählt als Lesen, solange der Leser offen ist; das erste Antippen gibt die Ansagen frei
  const regung = () => {
    uhr.regung();
    ansage.freigeben();
  };

  function verlassen() {
    eltern = false;
    if (onverlassen) onverlassen();
    else location.reload();
  }
</script>

<svelte:window onpointerdown={regung} onkeydown={regung} />

<!-- Erst wenn feststeht, was angeschlossen ist (Sprechdienst oder Stimmen des Geräts), kommt der Bereich auf den Schirm -->
{#if ich && anschluesse.geladen}
  <div class="kind" class:nacht={ruht} style:--k-taste="{ich.darstellung.tippflaeche_mm}mm" data-stufe={ich.profil.stufe}>
    {#if ruht}
      <Ruhe {ich} lesezeit={uhr.stand} onschloss={() => (eltern = true)} />
    {:else if ort.art === "lesen"}
      {#key ort.buch}
        <Kinderleser {ich} buch={ort.buch} {uhr} onzurueck={() => navigate("/")} />
      {/key}
    {:else if ort.art === "katze" && ich.katze.an}
      <Katzenname {ich} onzurueck={() => navigate("/")} />
    {:else}
      <Regal {ich} {uhr} onschloss={() => (eltern = true)} />
    {/if}
    {#if eltern}
      <Elterndialog einblick={ich.einblick} onverlassen={verlassen} onschliessen={() => (eltern = false)} />
    {/if}
  </div>
{:else}
  <div class="kind">
    <div></div>
    <div class="k-leer">
      {#if fehler}
        <i class="fa-solid fa-plug-circle-xmark" aria-hidden="true"></i>
        <span>{fehler}</span>
        <button class="k-taste quer" type="button" onclick={() => void frage()}><i class="fa-solid fa-rotate-right" aria-hidden="true"></i>Noch einmal</button>
      {:else}
        <i class="fa-solid fa-book-open fa-beat-fade" aria-hidden="true"></i>
      {/if}
    </div>
  </div>
{/if}
