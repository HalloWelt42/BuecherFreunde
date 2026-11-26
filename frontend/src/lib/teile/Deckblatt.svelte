<script lang="ts">
  // Das gestaltete Deckblatt (BF-59) als SVG. Es kommt aus lib/umschlag/gestaltet, das alles aus den Daten maskiert;
  // deshalb darf es als Markup hinein. Steht in einem .umschlag.
  import { gestaltetesBlatt, type Blattangaben } from "../umschlag/gestaltet";

  let { buch }: { buch: Blattangaben } = $props();

  let svg = $derived(gestaltetesBlatt(buch));
</script>

{@html svg}
