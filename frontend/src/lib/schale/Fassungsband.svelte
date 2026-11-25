<script lang="ts">
  import { fassung } from "../fassung.svelte";
  import Knopf from "../teile/Knopf.svelte";
</script>

{#if fassung.neu}
  <div class="band-fassung glas dicht" role="status">
    <span>Neue Fassung {fassung.neu} bereit</span>
    <Knopf text="Jetzt neu laden" symbol="rotate-right" haupt klein onclick={() => location.reload()} />
  </div>
{/if}

<style>
  .band-fassung {
    position: absolute;
    z-index: 65;
    left: 50%;
    bottom: 4.5rem;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 0.75rem;
    max-width: calc(100% - 2rem);
    padding: 0.5rem 0.5rem 0.5rem 0.875rem;
  }
</style>
