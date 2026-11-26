<!-- Die Katze des Kinderbereichs: samtpfote von hallowelt42 (github.com/HalloWelt42/samtpfote, LIZENZ.txt im Paket), als
     Abhängigkeit auf einem festen Stand eingebunden. Ihre Nennung "hallowelt42 / samtpfote" steht als eigene Zeile unter ihr,
     nie über ihr (credit-mode="external", Lizenz Punkt 2: mindestens gleichwertig sichtbar). Zustände: wach im Regal, schläft
     beim Lesen (eingeschlafen hält sie still und nimmt kein Tippen an), ruht auf dem Ruheschirm (schläft, lässt sich streicheln). -->
<script lang="ts">
  import type { Samtpfote } from "samtpfote/src/lib/widget.js";
  import { NENNUNG, SCHNURREN } from "./samtpfote";
  import { darstellung } from "../stand/darstellung.svelte";
  import type { Katzenzustand } from "./typen";

  let { name, zustand = "wach", schnurren = false, groesse = "7rem", nacht = false }: { name: string; zustand?: Katzenzustand; schnurren?: boolean; groesse?: string; nacht?: boolean } = $props();

  /** So lange braucht sie, bis sie ganz eingeschlafen ist; danach hält sie still */
  const EINSCHLAFEN_MS = 4500;

  let katze = $state<Samtpfote>();
  let fell = $derived(darstellung.dunkel || nacht ? "cream" : "black");
  let wort = $derived(name || "Katze");

  $effect(() => {
    const k = katze;
    if (!k) return;
    if (zustand === "wach") {
      k.removeAttribute("paused");
      return;
    }
    k.perform("sleeping");
    if (zustand === "ruht") return;
    // Beim Lesen: jede Regung des Kindes schläfert sie gleich wieder ein, bis sie still liegt
    const weiterschlafen = () => k.perform("sleeping");
    const arten = ["pointerdown", "keydown", "pointermove", "wheel"] as const;
    for (const a of arten) addEventListener(a, weiterschlafen, { passive: true });
    const still = setTimeout(() => {
      for (const a of arten) removeEventListener(a, weiterschlafen);
      k.setAttribute("paused", "");
    }, EINSCHLAFEN_MS);
    return () => {
      clearTimeout(still);
      for (const a of arten) removeEventListener(a, weiterschlafen);
      k.removeAttribute("paused");
    };
  });
</script>

<div class="k-katze" data-zustand={zustand} style:--cat-size={groesse}>
  <samt-pfote
    bind:this={katze}
    credit-mode="external"
    cat-name={wort}
    coat={fell}
    lighting={nacht ? "night" : "neutral"}
    sleep-after={zustand === "wach" ? undefined : "5"}
    sound-src={schnurren ? SCHNURREN : undefined}
    volume="35"
    inert={zustand === "schlaeft"}
    aria-label={zustand === "schlaeft" ? `${wort} schläft` : undefined}
  ></samt-pfote>
  <span class="k-nennung">{NENNUNG}</span>
</div>
