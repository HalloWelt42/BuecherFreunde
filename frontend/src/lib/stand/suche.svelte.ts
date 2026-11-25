// Suchart und Suchwort der Adresse /search
import { navigate, route } from "../router.svelte";
import { lies, merke } from "../speicher";
import { merkeBegriff, ladeVerlauf, leereVerlauf, vergissBegriff } from "../suchverlauf";

export type Suchart = "woerter" | "bedeutung" | "beides";

export const suchwerte: [Suchart, string][] = [["woerter", "Wörter"], ["bedeutung", "Bedeutung"], ["beides", "Beides"]];

function gueltig(wert: string | undefined): wert is Suchart {
  return suchwerte.some(([w]) => w === wert);
}

const gemerkt = lies("suche.art", "beides");

class Suche {
  #art = $state<Suchart>(gueltig(gemerkt) ? gemerkt : "beides");
  verlauf = $state<string[]>(ladeVerlauf());

  /** Das Suchwort der Adresse, nur auf /search */
  wort = $derived(route.path === "/search" ? (route.params as Record<string, string>).q ?? "" : "");

  get art(): Suchart {
    const inAdresse = route.path === "/search" ? (route.params as Record<string, string>).art : undefined;
    return gueltig(inAdresse) ? inAdresse : this.#art;
  }

  waehleArt(art: Suchart): void {
    this.#art = art;
    merke("suche.art", art);
    if (this.wort) navigate(this.adresse(this.wort), true);
  }

  adresse(wort: string): string {
    return `/search?${new URLSearchParams({ q: wort, art: this.#art })}`;
  }

  suche(wort: string): void {
    const sauber = wort.trim();
    if (!sauber) return;
    this.merke(sauber);
    navigate(this.adresse(sauber));
  }

  merke(wort: string): void {
    this.verlauf = merkeBegriff(this.verlauf, wort);
  }

  vergiss(wort: string): void {
    this.verlauf = vergissBegriff(this.verlauf, wort);
  }

  leere(): void {
    this.verlauf = leereVerlauf();
  }
}

export const suche = new Suche();
