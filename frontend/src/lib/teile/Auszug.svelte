<script lang="ts">
  import { zerlege } from "../auszug";
  let { text }: { text: string } = $props();
</script>

{#each zerlege(text) as stueck, n (n)}{#if stueck.markiert}<mark>{stueck.text}</mark>{:else}{stueck.text}{/if}{/each}
