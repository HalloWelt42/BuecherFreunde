<script>
  let { visible = $bindable(false) } = $props();

  let activeCrypto = $state(null);
  let copyFeedback = $state(null);

  const cryptos = [
    { id: 'btc', label: 'BITCOIN', symbol: 'BTC', icon: 'fa-brands fa-bitcoin', color: '#f7931a', address: 'bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr', qr: '/images/btc-qr.svg' },
    { id: 'doge', label: 'DOGECOIN', symbol: 'DOGE', icon: 'fa-solid fa-dog', color: '#c3a634', address: 'DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV', qr: '/images/doge-qr.svg' },
    { id: 'eth', label: 'ETHEREUM', symbol: 'ETH', icon: 'fa-brands fa-ethereum', color: '#627eea', address: '0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27', qr: '/images/eth-qr.svg' }
  ];

  function close() {
    activeCrypto = null;
    visible = false;
  }

  function selectCrypto(id) {
    activeCrypto = activeCrypto === id ? null : id;
  }

  async function copyAddress(address) {
    try {
      await navigator.clipboard.writeText(address);
      copyFeedback = address;
      setTimeout(() => { copyFeedback = null; }, 2000);
    } catch {
      // still
    }
  }

  function onBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function onKeydown(e) {
    if (e.key === 'Escape') close();
  }
</script>

{#if visible}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="bedanken-overlay" onclick={onBackdropClick} onkeydown={onKeydown}>
    <div class="bedanken-panel">
      <button class="close-btn" onclick={close} title="Schließen">
        <i class="fa-solid fa-xmark"></i>
      </button>

      <div class="intro">
        <div class="intro-icon">
          <i class="fa-solid fa-heart"></i>
        </div>
        <h2 class="intro-title">BücherFreunde unterstützen</h2>
        <p class="intro-text">
          BücherFreunde ist ein nicht-kommerzielles Open-Source-Projekt.
          Wenn es dir gefällt und du die Entwicklung unterstützen möchtest,
          freue ich mich über eine kleine Aufmerksamkeit.
        </p>
      </div>

      <a href="https://ko-fi.com/HalloWelt42" target="_blank" rel="noopener" class="kofi-btn">
        <i class="fa-solid fa-mug-hot"></i>
        <span>Unterstütze mich auf Ko-fi</span>
      </a>

      <div class="divider">
        <span class="divider-line"></span>
        <span class="divider-label">ODER PER KRYPTOWÄHRUNG</span>
        <span class="divider-line"></span>
      </div>

      <div class="crypto-cards">
        {#each cryptos as crypto}
          <button
            class="crypto-card"
            class:active={activeCrypto === crypto.id}
            onclick={() => selectCrypto(crypto.id)}
          >
            <div class="crypto-icon" style="--crypto-color: {crypto.color}">
              <i class={crypto.icon}></i>
            </div>
            <span class="crypto-name">{crypto.symbol}</span>
            <span class="crypto-led" class:on={activeCrypto === crypto.id}></span>
          </button>
        {/each}
      </div>

      {#each cryptos as crypto}
        {#if activeCrypto === crypto.id}
          <div class="crypto-detail">
            <div class="crypto-qr">
              <img src={crypto.qr} alt="{crypto.symbol} QR Code" />
            </div>
            <div class="crypto-info">
              <span class="crypto-label">{crypto.label}</span>
              <code class="crypto-address">{crypto.address}</code>
              <button
                class="copy-btn"
                onclick={() => copyAddress(crypto.address)}
              >
                <i class="fa-solid {copyFeedback === crypto.address ? 'fa-check' : 'fa-copy'}"></i>
                <span>{copyFeedback === crypto.address ? 'KOPIERT' : 'ADRESSE KOPIEREN'}</span>
              </button>
            </div>
          </div>
        {/if}
      {/each}

      <div class="bedanken-footer">
        <i class="fa-solid fa-heart"></i>
        Vielen Dank für deine Unterstützung!
      </div>
    </div>
  </div>
{/if}

<style>
  .bedanken-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .bedanken-panel {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    padding: 2rem 2.5rem;
    max-width: 560px;
    width: 90vw;
    max-height: 90vh;
    overflow-y: auto;
    background: var(--color-bg-primary);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.25s ease;
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .close-btn {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid transparent;
    border-radius: 6px;
    color: var(--color-text-muted);
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.12s;
  }

  .close-btn:hover {
    background: var(--glass-bg-btn);
    color: var(--color-text-primary);
    border-color: var(--glass-border);
  }

  /* Intro */
  .intro {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.625rem;
    text-align: center;
    max-width: 460px;
  }

  .intro-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    color: #cc2244;
  }

  .intro-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--color-text-primary);
    margin: 0;
  }

  .intro-text {
    font-size: 0.8125rem;
    line-height: 1.7;
    color: var(--color-text-muted);
    margin: 0;
  }

  /* Ko-fi */
  .kofi-btn {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.75rem 2rem;
    background: var(--color-accent);
    border: none;
    border-radius: 999px;
    color: #fff;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .kofi-btn:hover {
    filter: brightness(1.15);
    transform: translateY(-1px);
  }

  .kofi-btn i {
    font-size: 1rem;
  }

  /* Divider */
  .divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    max-width: 500px;
  }

  .divider-line {
    flex: 1;
    height: 1px;
    background: var(--color-border);
  }

  .divider-label {
    font-size: 0.5625rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  /* Crypto Cards */
  .crypto-cards {
    display: flex;
    gap: 0.75rem;
  }

  .crypto-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem 1.75rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .crypto-card:hover {
    background: var(--glass-bg-btn);
    transform: translateY(-2px);
  }

  .crypto-card.active {
    border-color: var(--color-accent);
    background: var(--glass-bg-btn);
    transform: none;
  }

  .crypto-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    color: var(--crypto-color);
    transition: all 0.15s ease;
  }

  .crypto-name {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: var(--color-text-secondary);
  }

  .crypto-card.active .crypto-name {
    color: var(--color-text-primary);
  }

  .crypto-led {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-text-muted);
    opacity: 0.3;
    transition: all 0.2s ease;
  }

  .crypto-led.on {
    background: #22c55e;
    opacity: 1;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
  }

  /* Detail */
  .crypto-detail {
    display: flex;
    gap: 1.25rem;
    align-items: center;
    padding: 1.25rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    width: 100%;
    max-width: 500px;
  }

  .crypto-qr {
    width: 128px;
    height: 128px;
    flex-shrink: 0;
    background: #fff;
    border-radius: 6px;
    padding: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .crypto-qr img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .crypto-info {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 0;
    flex: 1;
  }

  .crypto-label {
    font-size: 0.8125rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--color-text-primary);
  }

  .crypto-address {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-secondary);
    background: var(--color-bg-primary);
    padding: 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    word-break: break-all;
    line-height: 1.5;
  }

  .copy-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    align-self: flex-start;
    padding: 0.5rem 1rem;
    background: var(--color-bg-primary);
    border: 1px solid var(--color-border);
    border-radius: 999px;
    color: var(--color-text-secondary);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .copy-btn:hover {
    border-color: var(--color-accent);
    color: var(--color-accent);
  }

  /* Footer */
  .bedanken-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  .bedanken-footer i {
    color: #cc2244;
  }
</style>
