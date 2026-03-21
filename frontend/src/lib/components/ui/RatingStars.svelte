<script>
  let { rating = 0, interactive = false, size = "normal", onRate = null } = $props();

  function handleClick(star) {
    if (interactive && onRate) {
      onRate(star === rating ? 0 : star);
    }
  }
</script>

<div class="stars" class:interactive class:small={size === "small"}>
  {#each [1, 2, 3, 4, 5] as star (star)}
    <button
      class="star"
      class:filled={star <= rating}
      onclick={() => handleClick(star)}
      disabled={!interactive}
      title="{star} Stern{star > 1 ? 'e' : ''}"
    >
      <span class="star-stack">
        <i class="fa-solid fa-star star-outline"></i>
        <i class="{star <= rating ? 'fa-solid' : 'fa-regular'} fa-star star-front"></i>
      </span>
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
    padding: 0;
    line-height: 1;
    font-size: 0.875rem;
  }

  .stars.small .star {
    font-size: 0.6875rem;
  }

  .star-stack {
    position: relative;
    display: inline-block;
  }

  .star-outline {
    color: rgba(0, 0, 0, 0.7);
    font-size: 1.15em;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  .star-front {
    position: relative;
    z-index: 1;
  }

  .star.filled .star-front {
    color: var(--color-warning);
  }

  .star:not(.filled) .star-front {
    color: rgba(255, 255, 255, 0.5);
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
