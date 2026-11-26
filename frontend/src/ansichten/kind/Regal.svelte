<script lang="ts">
  // Das Kinderregal: nur die freigegebenen Bücher. In den ersten Stufen sonst nichts (drei große Umschläge je Reihe); wer mehr
  // darf, bekommt Mein Regal, Lieblinge und Gelesen und die Suche im eigenen Regal. "Gelesen" ist der ruhige Rückblick: die
  // Umschläge der fertigen Bücher mit dem Tag, ohne Punkte.
  // Klein: große Umschläge und Tasten, unten die Uhr und die Katze. Groß (BF-88): im Stil der App, Kopf und Bühne aus Glas, oben
  // das zuletzt gelesene Buch mit Weiterlesen und die Regale (beides steht, nur das Regal rollt), die Bücher auf Glasböden, die
  // Uhr und die Katze klein im Kopf; die Suche bleibt auch unter Gelesen stehen.
  import { tick } from "svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import { buch as buchansage, HINWEIS, TASTE } from "../../lib/kind/ansagen";
  import { holeRegal, type Regalart } from "../../lib/kind/api";
  import { wannGelesen } from "../../lib/kind/datum";
  import Katze from "../../lib/kind/Katze.svelte";
  import Kinderuhr from "../../lib/kind/Kinderuhr.svelte";
  import type { Lesezeituhr } from "../../lib/kind/lesezeit.svelte";
  import { weiterzulesen } from "../../lib/kind/stelle";
  import type { Ich } from "../../lib/kind/typen";
  import { lesestand, standText } from "../../lib/lesestand";
  import { navigate, route } from "../../lib/router.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import type { Buch } from "../../lib/typen";
  import Buchkachel from "./Buchkachel.svelte";
  import Wer from "./Wer.svelte";

  let { ich, uhr, onschloss }: { ich: Ich; uhr: Lesezeituhr; onschloss: () => void } = $props();

  const f = $derived(ich.faehigkeiten);
  const gross = $derived(ich.gestaltung === "gross");
  /** Die Regale, die das Kind hat; nur eines heißt: keine Tasten */
  let regale = $derived<[Regalart, string, string][]>([
    ["alle", "Mein Regal", "book"],
    ...(f.has("favoriten") ? [["lieblinge", "Lieblinge", "heart"] as [Regalart, string, string]] : []),
    ...(f.has("gelesen") ? [["gelesen", "Gelesen", "circle-check"] as [Regalart, string, string]] : []),
  ]);
  const REGALANSAGE: Record<Regalart, string> = { alle: TASTE.meinRegal, lieblinge: TASTE.lieblinge, gelesen: TASTE.gelesen };
  let art = $derived<Regalart>(regale.some(([a]) => a === route.params.regal) ? (route.params.regal as Regalart) : "alle");
  /** Klein mit nur einem Regal und ohne Suche: noch größere Umschläge */
  let wenige = $derived(regale.length === 1 && !f.has("suche"));
  /** Die Suche steht in Klein nur über Mein Regal und den Lieblingen, in Groß auch über Gelesen */
  let mitSuche = $derived(f.has("suche") && (gross || art !== "gelesen"));

  let buecher = $state.raw<Buch[]>([]);
  /** Alle Bücher des Kindes, für Weiterlesen (Groß), auch wenn gerade ein anderes Regal offen ist */
  let alle = $state.raw<Buch[]>([]);
  let laedt = $state(true);
  let fehler = $state("");
  let suche = $state("");

  async function lade(welche: Regalart) {
    laedt = true;
    fehler = "";
    try {
      const liste = await holeRegal(welche);
      if (welche === "alle") alle = liste;
      if (welche !== art) return;
      buecher = welche === "gelesen" ? liste.toSorted((a, b) => (b.fertig_am ?? "").localeCompare(a.fertig_am ?? "")) : liste;
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    } finally {
      laedt = false;
    }
  }

  $effect(() => void lade(art));
  // Weiterlesen braucht alle Bücher, auch wenn das Regal mit Lieblingen oder Gelesen aufgeht
  $effect(() => {
    if (gross && art !== "alle" && !alle.length) holeRegal("alle").then((liste) => (alle = liste)).catch(() => undefined);
  });
  let weiter = $derived(gross ? weiterzulesen(alle) : null);

  const einfach = (t: string) => t.toLocaleLowerCase("de").normalize("NFD").replace(/\p{M}/gu, "");
  let gezeigt = $derived.by(() => {
    const s = einfach(suche.trim());
    if (!s || !mitSuche) return buecher;
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
  const wann = (buch: Buch) => (art === "gelesen" ? wannGelesen(buch.fertig_am ?? buch.last_read_at, jetzt) : "");
</script>

{#snippet suchfeld(klasse: string, leeren: string)}
  <label class={klasse}>
    <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
    <input type="search" bind:value={suche} placeholder="Buch suchen" aria-label="Buch suchen" autocomplete="off" />
    {#if suche}<button class={leeren} type="button" aria-label="Suche leeren" onclick={() => (suche = "")}><i class="fa-solid fa-xmark" aria-hidden="true"></i></button>{/if}
  </label>
{/snippet}

{#if gross}
  <header class="kopf glas milch">
    <span class="g-wer"><span class="k-bild" style:background={ich.profil.farbe} aria-hidden="true"><i class="fa-solid fa-{ich.profil.zeichen}"></i></span><span>{ich.profil.name}</span></span>
    <div class="g-rechts">
      <Kinderuhr {uhr} kopf={ich.uhr} ruheAb={ich.lesezeit.ruhe_ab} onsage={(folge) => void ansage.hinweis(folge)} />
      {#if ich.katze.an}<Katze name={ich.katze.name} schnurren={ich.katze.schnurren} groesse="2.25rem" />{/if}
      <button class="knopf nur" type="button" aria-label="Für Eltern" title="Für Eltern" onclick={schloss}><i class="fa-solid fa-lock" aria-hidden="true"></i></button>
    </div>
  </header>

  <div class="buehne glas klar">
    {#if weiter || regale.length > 1 || f.has("suche")}
      <div class="g-oben">
        {#if weiter}
          <div class="g-weiter platte">
            <Umschlag buch={weiter} />
            <span class="g-text-weiter">
              <b>{weiter.title}</b>
              {#if weiter.author}<span class="leise">{weiter.author}</span>{/if}
              <Balken anteil={lesestand(weiter).anteil} name="Lesestand" />
              <span class="leise zahl">{standText(weiter)}</span>
            </span>
            <button class="knopf haupt" type="button" onclick={() => oeffne(weiter!)}><i class="fa-solid fa-book-open" aria-hidden="true"></i><span>Weiterlesen</span></button>
          </div>
        {/if}
        {#if regale.length > 1 || f.has("suche")}
          <div class="g-werkzeug" class:ohne-suche={!f.has("suche")}>
            {#if regale.length > 1}
              <div class="segment g-regalwahl" role="group" aria-label="Regale" style:--n={regale.length}>
                {#each regale as [a, name, zeichen] (a)}
                  <button type="button" aria-pressed={art === a} onclick={() => waehle(a)}><i class="fa-solid fa-{zeichen}" aria-hidden="true"></i><span>{name}</span></button>
                {/each}
              </div>
            {/if}
            {#if mitSuche}{@render suchfeld("g-suche", "knopf nur frei")}{/if}
          </div>
        {/if}
      </div>
    {/if}

    <div class="rollen g-regalflaeche">
      {#if fehler}
        <Zustand art="fehler" text={fehler} onerneut={() => void lade(art)} />
      {:else if !laedt && !gezeigt.length}
        <Zustand text={leerText} />
      {:else}
        <div class="regal g-regal" aria-busy={laedt}>
          {#each gezeigt as buch (buch.id)}
            {@const s = lesestand(buch)}
            {@const unter = wann(buch)}
            <div class="band">
              <button class="flaeche" type="button" aria-label={buch.title} onclick={() => oeffne(buch)}>
                <span class="stand"><Umschlag {buch} /></span>
                <span class="boden"></span>
                <span class="schild"><b>{buch.title}</b>{#if unter}<small>{unter}</small>{:else if s.angefangen && s.anteil < 1}<Balken anteil={s.anteil} name="Lesestand" />{/if}</span>
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
{:else}
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
        {#if mitSuche}{@render suchfeld("k-suche", "k-schloss")}{/if}
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
      <div class="k-regal" class:gross={wenige} aria-busy={laedt}>
        {#each gezeigt as buch (buch.id)}
          <Buchkachel {buch} unter={wann(buch)} onwahl={oeffne} />
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
        <Katze name={ich.katze.name} schnurren={ich.katze.schnurren} groesse={wenige ? "clamp(5rem, 12vw, 9rem)" : "clamp(4.5rem, 10vw, 7.5rem)"} />
      </div>
    {/if}
  </footer>
{/if}
