<script lang="ts">
  // Das Kinderregal: nur die freigegebenen Bücher als große Umschläge. In den ersten Stufen sonst nichts (drei große Umschläge
  // je Reihe); wer mehr darf, bekommt drei gleich große Tasten (Mein Regal, Lieblinge, Gelesen) und die Suche im eigenen Regal.
  // "Gelesen" ist der ruhige Rückblick: die Umschläge der fertigen Bücher mit dem Tag, ohne Punkte. Unten wartet die Katze.
  import { tick } from "svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import { buch as buchansage, HINWEIS, TASTE } from "../../lib/kind/ansagen";
  import { holeRegal, type Regalart } from "../../lib/kind/api";
  import { wannGelesen } from "../../lib/kind/datum";
  import Katze from "../../lib/kind/Katze.svelte";
  import Kinderuhr from "../../lib/kind/Kinderuhr.svelte";
  import type { Lesezeituhr } from "../../lib/kind/lesezeit.svelte";
  import type { Ich } from "../../lib/kind/typen";
  import { navigate, route } from "../../lib/router.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import type { Buch } from "../../lib/typen";
  import Buchkachel from "./Buchkachel.svelte";
  import Wer from "./Wer.svelte";

  let { ich, uhr, onschloss }: { ich: Ich; uhr: Lesezeituhr; onschloss: () => void } = $props();

  const f = $derived(ich.faehigkeiten);
  /** Die Regale, die das Kind hat; nur eines heißt: keine Tasten */
  let regale = $derived<[Regalart, string, string][]>([
    ["alle", "Mein Regal", "book"],
    ...(f.has("favoriten") ? [["lieblinge", "Lieblinge", "heart"] as [Regalart, string, string]] : []),
    ...(f.has("gelesen") ? [["gelesen", "Gelesen", "circle-check"] as [Regalart, string, string]] : []),
  ]);
  const REGALANSAGE: Record<Regalart, string> = { alle: TASTE.meinRegal, lieblinge: TASTE.lieblinge, gelesen: TASTE.gelesen };
  let art = $derived<Regalart>(regale.some(([a]) => a === route.params.regal) ? (route.params.regal as Regalart) : "alle");
  let gross = $derived(regale.length === 1 && !f.has("suche"));

  let buecher = $state.raw<Buch[]>([]);
  let laedt = $state(true);
  let fehler = $state("");
  let suche = $state("");

  async function lade(welche: Regalart) {
    laedt = true;
    fehler = "";
    try {
      const liste = await holeRegal(welche);
      if (welche !== art) return;
      buecher = welche === "gelesen" ? liste.toSorted((a, b) => (b.fertig_am ?? "").localeCompare(a.fertig_am ?? "")) : liste;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      laedt = false;
    }
  }

  $effect(() => void lade(art));

  const einfach = (t: string) => t.toLocaleLowerCase("de").normalize("NFD").replace(/\p{M}/gu, "");
  let gezeigt = $derived.by(() => {
    const s = einfach(suche.trim());
    if (!s || !f.has("suche") || art === "gelesen") return buecher;
    return buecher.filter((b) => einfach(`${b.title} ${b.author}`).includes(s));
  });

  function oeffne(buch: Buch) {
    // Noch im Tippen: so darf das Vorlesen gleich danach klingen
    vorlesen.entsperre();
    navigate(`/book/${buch.id}/read`);
    void ansage.taste([buchansage(buch.id)]);
  }

  function waehle(neu: Regalart) {
    suche = "";
    navigate(neu === "alle" ? "/" : `/?regal=${neu}`, true);
    void ansage.taste([REGALANSAGE[neu]]);
  }

  function schloss() {
    onschloss();
    void ansage.taste([TASTE.schloss]);
    void ansage.hinweis([HINWEIS.fragEltern]);
  }

  // Was sonst nur dasteht, wird vorgesprochen: ein leeres Regal
  let leerText = $derived(
    !laedt && !fehler && !gezeigt.length
      ? suche ? "Kein Buch gefunden." : art === "lieblinge" ? "Noch keine Lieblinge." : art === "gelesen" ? "Noch kein Buch zu Ende gelesen." : "Noch keine Bücher. Frag deine Eltern."
      : "",
  );
  let leerAnsage = $derived(suche ? HINWEIS.sucheLeer : art === "lieblinge" ? HINWEIS.lieblingeLeer : art === "gelesen" ? HINWEIS.gelesenLeer : HINWEIS.regalLeer);
  $effect(() => {
    const folge = leerText ? [leerAnsage] : null;
    if (folge) void tick().then(() => ansage.hinweis(folge));
  });

  const jetzt = new Date();
</script>

<header class="k-kopf">
  <Wer profil={ich.profil} />
  <div class="k-rechts">
    <button class="k-schloss" type="button" aria-label="Für Eltern" onclick={schloss}><i class="fa-solid fa-lock" aria-hidden="true"></i></button>
  </div>
</header>

<div class="k-mitte mit-regal">
  {#if regale.length > 1 || f.has("suche")}
    <div class="k-regalkopf">
      {#if regale.length > 1}
        <div class="k-regalwahl" role="tablist" aria-label="Regale">
          {#each regale as [a, name, zeichen] (a)}
            <button class="k-taste quer" class:an={art === a} type="button" role="tab" aria-selected={art === a} onclick={() => waehle(a)}><i class="fa-solid fa-{zeichen}" aria-hidden="true"></i>{name}</button>
          {/each}
        </div>
      {/if}
      {#if f.has("suche") && art !== "gelesen"}
        <label class="k-suche">
          <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
          <input type="search" bind:value={suche} placeholder="Buch suchen" aria-label="Buch suchen" autocomplete="off" />
          {#if suche}<button class="k-schloss" type="button" aria-label="Suche leeren" onclick={() => (suche = "")}><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>{/if}
        </label>
      {/if}
    </div>
  {/if}

  {#if fehler}
    <div class="k-leer">
      <i class="fa-solid fa-plug-circle-xmark" aria-hidden="true"></i>
      <span>{fehler}</span>
      <button class="k-taste quer" type="button" onclick={() => void lade(art)}><i class="fa-solid fa-rotate-right" aria-hidden="true"></i>Noch einmal</button>
    </div>
  {:else if !laedt && !gezeigt.length}
    <div class="k-leer">
      <i class="fa-{suche ? 'solid fa-magnifying-glass' : art === 'lieblinge' ? 'regular fa-heart' : art === 'gelesen' ? 'regular fa-circle-check' : 'solid fa-book'}" aria-hidden="true"></i><span>{leerText}</span>
    </div>
  {:else}
    <div class="k-regal" class:gross aria-busy={laedt}>
      {#each gezeigt as buch (buch.id)}
        <Buchkachel {buch} unter={art === "gelesen" ? wannGelesen(buch.fertig_am ?? buch.last_read_at, jetzt) : ""} onwahl={oeffne} />
      {/each}
    </div>
  {/if}
</div>

<footer class="k-fuss mit-katze">
  {#if art !== "gelesen"}<Kinderuhr {uhr} ruheAb={ich.lesezeit.ruhe_ab} mitText={ich.profil.stufe !== "vorlesen"} onsage={(folge) => void ansage.hinweis(folge)} />{/if}
  {#if ich.katze.an}
    <div class="k-katzenplatz">
      <a class="k-taste quer k-katzenname" href="/katze" aria-label={ich.katze.name ? `${ich.katze.name}, Namen ändern` : "Der Katze einen Namen geben"}>
        <i class="fa-solid fa-pen" aria-hidden="true"></i><span>{ich.katze.name || "?"}</span>
      </a>
      <Katze name={ich.katze.name} schnurren={ich.katze.schnurren} groesse={gross ? "clamp(5rem, 12vw, 9rem)" : "clamp(4.5rem, 10vw, 7.5rem)"} />
    </div>
  {/if}
</footer>
