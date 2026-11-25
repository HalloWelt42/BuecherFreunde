<script module lang="ts">
  export interface Vergleichszeile {
    schluessel: string;
    feld: string;
    alt: string;
    neu: string;
    gewaehlt: boolean;
    /** Kein Unterschied: nichts zu übernehmen */
    gleich: boolean;
    bildAlt?: string;
    bildNeu?: string;
  }
</script>

<script lang="ts">
  // Bisher und neu nebeneinander, je Feld ein Häkchen. Am Telefon wird jede Zeile ein Block.
  import Bildvergleich from "./Bildvergleich.svelte";
  import Haekchen from "./Haekchen.svelte";

  let { zeilen, onwahl, gesperrt = false }: { zeilen: Vergleichszeile[]; onwahl: (schluessel: string, an: boolean) => void; gesperrt?: boolean } = $props();
</script>

<table class="tabelle vergleich">
  <thead>
    <tr><th><span class="nur-vorlesen">Übernehmen</span></th><th>Feld</th><th>Bisher</th><th>Neu</th></tr>
  </thead>
  <tbody>
    {#each zeilen as z (z.schluessel)}
      <tr class:gleich={z.gleich}>
        <td class="wahl"><Haekchen an={z.gewaehlt && !z.gleich} gesperrt={z.gleich || gesperrt} name="{z.feld} übernehmen" onwahl={(an) => onwahl(z.schluessel, an)} /></td>
        <td class="feldname">{z.feld}</td>
        <td class="leise" data-spalte="Bisher">
          {#if z.bildAlt}<Bildvergleich adresse={z.bildAlt} name="{z.feld}, bisher" />{:else}<span class="wert">{z.alt || "leer"}</span>{/if}
        </td>
        <td data-spalte="Neu">
          {#if z.bildNeu}<Bildvergleich adresse={z.bildNeu} name="{z.feld}, neu" />{:else if z.gleich}<span class="wert">{z.neu || "leer"}</span>{:else}<mark class="wert">{z.neu || "leer"}</mark>{/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .vergleich {
    table-layout: fixed;
  }
  th:first-child {
    width: 2.5rem;
  }
  th:nth-child(2) {
    width: 20%;
  }
  td {
    overflow-wrap: anywhere;
  }
  .wahl {
    padding-right: 0;
  }
  .gleich .feldname {
    color: var(--tinte-3);
  }
  .wert {
    white-space: pre-line;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }
  @container app (max-width: 720px) {
    thead {
      display: none;
    }
    tr {
      display: grid;
      grid-template-columns: 2.25rem minmax(0, 1fr);
      padding: 0.5rem 0;
      border-top: 1px solid var(--linie);
    }
    tr:first-child {
      border-top: 0;
    }
    td {
      border-top: 0;
      padding: 0.125rem 0.25rem;
    }
    .wahl {
      grid-row: 1 / span 3;
    }
    .feldname {
      font-weight: 600;
      align-self: center;
    }
    td[data-spalte] {
      grid-column: 2;
    }
    td[data-spalte]::before {
      content: attr(data-spalte) ": ";
      font-size: 0.8125rem;
      color: var(--tinte-3);
    }
  }
</style>
