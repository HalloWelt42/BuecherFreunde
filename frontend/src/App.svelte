<script>
  import { route, matchRoute, handleLinkClick } from "./lib/router.svelte.js";
  import { ui } from "./lib/stores/ui.svelte.js";
  import { hasToken, onAuthError } from "./lib/api/client.js";
  import Header from "./lib/components/layout/Header.svelte";
  import Sidebar from "./lib/components/layout/Sidebar.svelte";
  import Footer from "./lib/components/layout/Footer.svelte";
  import ScratchPad from "./lib/components/shared/ScratchPad.svelte";
  import TokenLogin from "./lib/components/auth/TokenLogin.svelte";

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

<div class="app-layout" class:sidebar-collapsed={!ui.sidebarOpen} class:reader-fullscreen={ui.readerFullscreen}>
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
    z-index: 1;
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
