<script lang="ts">
  // Eine ISBN im Buch (BF-111): Nummer, Ausgabe, Zahl der Funde, andere Schreibweisen, Stufe, Fundstellen. Fremde Bücher kurz, je
  // Fundort eine Zeile mit den Seiten; ihr Titel steht schon in der Stufe. "Seite N" öffnet den Leser in einem neuen Tab, das
  // Formular bleibt, wie es ist.
  import { ersteMarkierung } from "../../lib/auszug";
  import { anzahl } from "../../lib/format";
  import Auszug from "../../lib/teile/Auszug.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { AUSGABEN, FUNDORTE, einstufung, formenzeile, fremd, jeFundort, pruefstand, ruhemeldung, type Isbnzeile } from "./isbn";
  import { stellenort, stellenziel } from "./stelle";
  import Stufenzeile from "./Stufenzeile.svelte";

  interface Eigenschaften {
    zeile: Isbnzeile;
    buch: { id: number; file_format: string };
    gruppe: string;
    an: boolean;
    /** nur die erste Fundstelle (viele Kandidaten) */
    kurz?: boolean;
    onwahl: () => void;
    onpruefe: () => void;
  }
  let { zeile, buch, gruppe, an, kurz = false, onwahl, onpruefe }: Eigenschaften = $props();

  let k = $derived(zeile.kandidat);
  let ausgabe = $derived(k.ausgabe ? AUSGABEN[k.ausgabe] : null);
  let andere = $derived(fremd(k));
  let stellen = $derived(kurz ? k.stellen.slice(0, 1) : k.stellen);
  let warnung = $derived(zeile.pruefung && pruefstand(zeile) === "erneut" ? ruhemeldung(zeile.pruefung) : "");
  /** Fremde: je Fundort die Seiten */
  let orte = $derived(jeFundort(k.stellen));
</script>

<div class="kandidat" class:gewaehlt={an}>
  <label class="wahl"><input type="radio" name={gruppe} checked={an} aria-label="{k.isbn} wählen" onchange={onwahl} /></label>
  <div class="kern">
    <div class="kopfzeile">
      <b class="isbn zahl">{k.isbn}</b>
      {#if ausgabe}<span class="marke-text art" title="Neben der Nummer steht {ausgabe.wort}"><Symbol name={ausgabe.symbol} />{ausgabe.wort}</span>{/if}
      <span class="leise zahl">{anzahl(k.funde, "Fund", "Funde")}</span>
      {#if k.formen.length}<span class="formen zahl">{formenzeile(k)}</span>{/if}
    </div>
    <Stufenzeile einstufung={einstufung(zeile)} stand={pruefstand(zeile)} prueft={zeile.prueft} {warnung} {onpruefe} />
    <div class="stellen">
      {#if andere}
        {#each orte as [ort, liste] (ort)}
          <div class="stelle fund fremd"><i></i><span class="ort"><span>{FUNDORTE[ort]}</span><span class="reihe seiten">{#each liste as s, n (n)}<Chip text={stellenort(buch, s)} href={stellenziel(buch, s, ersteMarkierung(s.ausschnitt))} titel="Im Leser öffnen" neu />{/each}</span></span></div>
        {/each}
      {:else}
        {#each stellen as s, n (n)}
          <div class="stelle fund"><i></i><span class="ort"><span>{FUNDORTE[s.fundort]}</span><Chip text={stellenort(buch, s)} href={stellenziel(buch, s, ersteMarkierung(s.ausschnitt))} titel="Im Leser öffnen" neu /></span><span class="zitat"><Auszug text={s.ausschnitt} /></span></div>
        {/each}
      {/if}
    </div>
  </div>
</div>
