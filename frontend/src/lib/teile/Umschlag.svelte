<script lang="ts">
  // Umschlag eines Buchs: das gestaltete Blatt, wenn der Server es so bestimmt (BF-59), sonst das Deckblatt vom Server.
  // Das Blatt steht auch für reine Textdateien ohne Bild und wenn das Bild ausbleibt.
  import { untrack } from "svelte";
  import { coverUrl } from "../api/books";
  import { formatName } from "../format";
  import { regalfarben } from "../schale/regalfarben";
  import type { Umschlagart } from "../typen";
  import { blattFarben, type Blattangaben } from "../umschlag/gestaltet";
  import Deckblatt from "./Deckblatt.svelte";

  interface Buchbild extends Blattangaben {
    updated_at?: string;
    cover_path?: string;
    cover_stand?: number;
    file_format?: string;
    umschlag?: Umschlagart;
  }
  let { buch, sofort = false, format = false }: { buch: Buchbild; sofort?: boolean; format?: boolean } = $props();

  let adresse = $derived(coverUrl(buch.id, buch.cover_stand || buch.updated_at));
  let fertig = $state("");
  let kaputt = $state("");
  let ohneBild = $derived((buch.cover_path === "" && ["txt", "md"].includes(buch.file_format ?? "")) || kaputt === adresse);
  let gestaltet = $derived(buch.umschlag === "gestaltet" || ohneBild);

  // Das Blatt gibt Licht und Regalwand seine Farben, wie ein Bild es beim Laden tut
  $effect(() => {
    if (!gestaltet) return;
    const id = buch.id;
    const farben = blattFarben(buch);
    untrack(() => regalfarben.nimm(id, farben));
  });

  function geladen(e: Event) {
    fertig = adresse;
    regalfarben.sammle(buch.id, e.currentTarget as HTMLImageElement);
  }
</script>

<span class="umschlag" class:leer={!gestaltet && fertig !== adresse}>
  {#if gestaltet}
    <Deckblatt {buch} />
  {:else}
    <img src={adresse} alt="" loading={sofort ? "eager" : "lazy"} decoding="async" draggable="false" onload={geladen} onerror={() => (kaputt = adresse)} />
  {/if}
  {#if format && buch.file_format}<span class="format">{formatName(buch.file_format)}</span>{/if}
</span>
