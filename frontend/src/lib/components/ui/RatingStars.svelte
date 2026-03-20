<script>
  let { rating = 0, interactive = false, onRate = null } = $props();

  function handleClick(star) {
    if (interactive && onRate) {
      onRate(star === rating ? 0 : star);
    }
  }
</script>

<div class="stars" class:interactive>
  {#each [1, 2, 3, 4, 5] as star (star)}
    <button
      class="star"
      class:filled={star <= rating}
      onclick={() => handleClick(star)}
      disabled={!interactive}
      title="{star} Stern{star > 1 ? 'e' : ''}"
    >
      {star <= rating ? "\u2605" : "\u2606"}
    </button>
  {/each}
</div>

<style>
  .stars {
    display: inline-flex;
    gap: 0.0625rem;
  }

  .star {
    background: none;
    border: none;
    font-size: 0.875rem;
    color: var(--color-warning);
    padding: 0;
    line-height: 1;
  }

  .star:not(.filled) {
    color: var(--color-text-muted);
  }

  .interactive .star {
    cursor: pointer;
  }

  .interactive .star:hover {
    transform: scale(1.2);
  }

  .star:disabled:not(.interactive *) {
    cursor: default;
  }
</style>
