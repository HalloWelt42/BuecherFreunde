<script>
  import { route, matchRoute, handleLinkClick } from "./lib/router.svelte.js";
  import { ui } from "./lib/stores/ui.svelte.js";
  import { hasToken, onAuthError, getToken } from "./lib/api/client.js";
  import Header from "./lib/components/layout/Header.svelte";
  import Sidebar from "./lib/components/layout/Sidebar.svelte";
  import Footer from "./lib/components/layout/Footer.svelte";
  import ScratchPad from "./lib/components/shared/ScratchPad.svelte";
  import TokenLogin from "./lib/components/auth/TokenLogin.svelte";
  import Toast from "./lib/components/ui/Toast.svelte";

  import Library from "./pages/Library.svelte";
  import BookDetail from "./pages/BookDetail.svelte";
  import Reader from "./pages/Reader.svelte";
  import SearchResults from "./pages/SearchResults.svelte";
  import CollectionView from "./pages/CollectionView.svelte";
  import Authors from "./pages/Authors.svelte";
  import AuthorDetail from "./pages/AuthorDetail.svelte";
  import Import from "./pages/Import.svelte";
  import Settings from "./pages/Settings.svelte";

  let showLogin = $state(!hasToken());

  onAuthError(() => {
    showLogin = true;
  });

  function onLoginSuccess() {
    showLogin = false;
    window.location.reload();
  }

  let bgUrl = $derived(
    ui.bgAktuellerDateiname
      ? `/api/config/design/hintergrund/${ui.bgAktuellerDateiname}?token=${encodeURIComponent(getToken())}`
      : null
  );

  const routeDefs = [
    { pattern: "/book/:id/read", component: Reader },
    { pattern: "/book/:id", component: BookDetail },
    { pattern: "/authors", component: Authors },
    { pattern: "/author/:id", component: AuthorDetail },
    { pattern: "/search", component: SearchResults },
    { pattern: "/collection/:id", component: CollectionView },
    { pattern: "/import", component: Import },
    { pattern: "/settings/*", component: Settings },
    { pattern: "/settings", component: Settings },
    { pattern: "/", component: Library },
  ];

  // route ist reaktives Objekt ($state in .svelte.js)
  let resolved = $derived.by(() => {
    const path = route.path;
    for (const def of routeDefs) {
      const match = matchRoute(def.pattern, path);
      if (match !== null) {
        const hasParams = Object.keys(match).length > 0;
        return { component: def.component, params: hasParams ? match : null };
      }
    }
    return null;
  });
</script>

{#if showLogin}
  <TokenLogin onSuccess={onLoginSuccess} />
{/if}

<svelte:document onclick={handleLinkClick} />

<div class="app-layout" class:sidebar-collapsed={!ui.sidebarOpen} class:reader-fullscreen={ui.readerFullscreen} class:has-bg={bgUrl}>
  {#if bgUrl}
    <div class="app-bg" style="background-image: url({bgUrl})"></div>
    <div class="app-bg-overlay"></div>
  {/if}
  <div class="grid-header">
    <Header />
  </div>

  <div class="grid-sidebar">
    <Sidebar currentPath={route.path} />
  </div>

  <main class="grid-main">
    {#if resolved}
      {#key route.path}
        {#if resolved.params}
          <resolved.component params={resolved.params} />
        {:else}
          <resolved.component />
        {/if}
      {/key}
    {/if}
  </main>

  <div class="grid-footer">
    <Footer />
  </div>
</div>

<ScratchPad visible={ui.scratchPadOpen} onClose={() => ui.scratchPadOpen = false} />
<Toast />

<style>
  .app-layout {
    display: grid;
    grid-template-areas:
      "header header"
      "sidebar main"
      "footer footer";
    grid-template-columns: var(--sidebar-width) 1fr;
    grid-template-rows: var(--header-height) 1fr auto;
    height: 100vh;
    overflow: hidden;
    position: relative;
  }

  .app-bg {
    position: fixed;
    inset: 0;
    z-index: 0;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    filter: blur(6px) saturate(1.2);
    transform: scale(1.02);
    pointer-events: none;
  }

  .app-bg-overlay {
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background: rgba(255, 255, 255, 0.55);
  }

  :global(:root.dark) .app-bg-overlay {
    background: rgba(0, 0, 0, 0.55);
  }

  /* Body transparent bei aktivem Hintergrundbild */
  :global(body:has(.app-layout.has-bg)) {
    background-color: transparent;
  }

  .app-layout.sidebar-collapsed {
    grid-template-columns: 0 1fr;
  }

  .app-layout.sidebar-collapsed .grid-sidebar {
    width: 0;
    padding: 0;
    border: none;
  }

  .grid-header {
    grid-area: header;
    z-index: 20;
  }

  .grid-sidebar {
    grid-area: sidebar;
    overflow-y: auto;
    overflow-x: hidden;
    transition: width 0.2s ease, padding 0.2s ease;
    width: var(--sidebar-width);
    z-index: 10;
    position: relative;
  }

  .grid-main {
    grid-area: main;
    padding: 1.5rem;
    overflow-y: auto;
    overflow-x: hidden;
    z-index: 2;
    position: relative;
  }

  .grid-footer {
    grid-area: footer;
    z-index: 50;
  }

  /* Vollbild-Lesemodus: Header, Sidebar, Footer ausblenden */
  .app-layout.reader-fullscreen {
    grid-template-areas: "main";
    grid-template-columns: 1fr;
    grid-template-rows: 1fr;
  }

  .app-layout.reader-fullscreen .grid-header,
  .app-layout.reader-fullscreen .grid-sidebar,
  .app-layout.reader-fullscreen .grid-footer {
    display: none;
  }

  .app-layout.reader-fullscreen .grid-main {
    padding: 0;
  }
</style>
