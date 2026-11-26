// Die Muster der gestalteten Blätter (BF-59), wie in der abgenommenen Stilprobe: je Muster drei Farben, Titel, Autor
// und Jahr. Text kommt nur über lib/umschlag/satz hinein, dort wird er maskiert.
import type { Dreiklang } from "../farben";
import { autorzeile, block, GROTESK, H, klein, maskiere, SERIF, titel } from "./satz";

/** Was ein Blatt zeigt; der Titel ist schon gekürzt und nie leer */
export interface Blatt {
  titel: string;
  autor: string;
  jahr: string;
}

export type Muster = (b: Blatt, farben: Dreiklang) => string;

const jahrzahl = (jahr: string, x: number, y: number, grad: number, farbe: string): string =>
  jahr ? `<text x="${x}" y="${y}" text-anchor="end" font-family="${GROTESK}" font-weight="700" font-size="${grad}" fill="${farbe}">${maskiere(jahr)}</text>` : "";

// --- Bücher ---

const typo: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/><rect x="18" y="30" width="46" height="7" fill="${c}"/>${titel(b.titel, 18, 72, d, { max: 30, bis: H - 44 })}${autorzeile(b.autor, 18, H - 20, d)}`;

const leinen: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/><path d="${Array.from({ length: 50 }, (_, i) => `M0 ${i * 6.2}H200`).join("")}" stroke="${c}" stroke-opacity=".5" stroke-width="1.4"/><path d="${Array.from({ length: 34 }, (_, i) => `M${i * 6} 0V${H}`).join("")}" stroke="#000" stroke-opacity=".13"/><rect x="18" y="18" width="164" height="${H - 36}" fill="none" stroke="${d}" stroke-width="1.6"/><rect x="23" y="23" width="154" height="${H - 46}" fill="none" stroke="${d}" stroke-width=".7"/>${titel(b.titel, 100, 92, d, { anker: "middle", breit: 138, n: 12, max: 25, bis: H - 124 })}<path d="M78 ${H - 92}q22 -16 44 0q-22 16 -44 0M100 ${H - 112}v40" fill="none" stroke="${d}" stroke-width="1.4"/>${autorzeile(b.autor, 100, H - 40, d, "middle", 150)}`;

const wellen: Muster = (b, [a, c, d]) => {
  const schrift = d === "#253646" ? d : "#fff";
  return `<rect width="200" height="${H}" fill="${a}"/>${[0, 1, 2, 3, 4].map((i) => `<path d="M0 ${H * 0.52 + i * 27}q50 ${-38 + i * 9} 100 0t100 0V${H}H0Z" fill="${i % 2 ? d : c}" fill-opacity="${0.34 + i * 0.13}"/>`).join("")}${titel(b.titel, 16, 48, schrift, { max: 25, bis: 130 })}${autorzeile(b.autor, 16, 26, schrift)}`;
};

const raster: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/>${Array.from({ length: 70 }, (_, i) => {
    const x = 14 + (i % 10) * 19;
    const y = 16 + Math.floor(i / 10) * 19;
    return `<circle cx="${x}" cy="${y}" r="${(2 + 6 * Math.abs(Math.sin(i * 0.37))).toFixed(1)}" fill="${c}"/>`;
  }).join("")}<rect y="${H - 128}" width="200" height="128" fill="${d}"/>${titel(b.titel, 16, H - 92, a, { schrift: GROTESK, f: 0.6, max: 25, bis: H - 36 })}${autorzeile(b.autor, 16, H - 16, a)}`;

const teilung: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/><path d="M0 ${H * 0.64}L200 ${H * 0.34}V${H}H0Z" fill="${c}"/><path d="M0 ${H * 0.64}L200 ${H * 0.34}v14L0 ${H * 0.64 + 14}Z" fill="${d}" fill-opacity=".5"/>${titel(b.titel, 16, 46, d, { schrift: GROTESK, f: 0.6, max: 27, bis: H * 0.64 - 12 })}${autorzeile(b.autor, 16, H - 18, d)}`;

/** Kreise, Titel eingepasst in die Fläche unten; sie wächst mit dem Titel */
const kreis: Muster = (b, [a, c, d]) => {
  const t = block(b.titel, 16, 0, a, { breit: 168, hoehe: 78, max: 24, f: 0.6, anker: "start" });
  const box = Math.max(104, t.hoehe + 50);
  return `<rect width="200" height="${H}" fill="${a}"/>${[92, 74, 56, 38, 20].map((r, i) => `<circle cx="132" cy="102" r="${r}" fill="none" stroke="${c}" stroke-width="${i === 4 ? 14 : 5}" stroke-opacity="${0.5 + i * 0.1}"/>`).join("")}<rect y="${H - box}" width="200" height="${box}" fill="${d}" fill-opacity=".94"/><g transform="translate(0 ${H - box + 16})">${t.svg}</g>${autorzeile(b.autor, 16, H - 16, a)}`;
};

const sterne: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/>${[150, 118, 86, 54].map((r) => `<circle cx="100" cy="${H - 40}" r="${r}" fill="none" stroke="${c}" stroke-width="1.5"/>`).join("")}${Array.from({ length: 46 }, (_, i) => `<circle cx="${(i * 53) % 200}" cy="${(i * 89) % (H - 20)}" r="${(0.6 + (i % 5) * 0.42).toFixed(1)}" fill="${d}"/>`).join("")}${titel(b.titel, 16, 48, d, { max: 25, bis: H - 44 })}${autorzeile(b.autor, 16, H - 16, d)}`;

const globus: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/><circle cx="100" cy="${H - 106}" r="78" fill="${c}"/>${[78, 52, 24].map((r) => `<ellipse cx="100" cy="${H - 106}" rx="${r}" ry="78" fill="none" stroke="${a}" stroke-width="1.6"/>`).join("")}${[-48, -24, 0, 24, 48].map((y) => `<path d="M${100 - Math.sqrt(6084 - y * y)} ${H - 106 + y}H${100 + Math.sqrt(6084 - y * y)}" stroke="${a}" stroke-width="1.6"/>`).join("")}<path d="M42 ${H - 130}q60 -54 116 22" fill="none" stroke="${d}" stroke-width="3" stroke-dasharray="7 5"/>${titel(b.titel, 16, 38, d, { max: 24, bis: H - 194 })}${autorzeile(b.autor, 16, H - 10, d)}`;

/** Berge, Titel eingepasst in den Himmel */
const berge: Muster = (b, [a, c, d]) => {
  const t = block(b.titel, 16, 26, d, { breit: 168, hoehe: H * 0.42 - 40, max: 29, f: 0.62, schrift: SERIF, w: 700, anker: "start" });
  return `<rect width="200" height="${H}" fill="${c}"/><circle cx="150" cy="${H * 0.5}" r="24" fill="${d}"/><path d="M0 ${H * 0.62}L52 ${H * 0.44}L98 ${H * 0.6}L150 ${H * 0.46}L200 ${H * 0.6}V${H}H0Z" fill="${a}" fill-opacity=".62"/><path d="M0 ${H * 0.78}L70 ${H * 0.6}L128 ${H * 0.76}L200 ${H * 0.64}V${H}H0Z" fill="${a}"/>${t.svg}${autorzeile(b.autor, 16, H - 18, d)}`;
};

const blatt: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${d}"/><path d="M100 ${H - 22}C20 ${H - 92} 34 ${H * 0.42} 100 ${H * 0.36}C166 ${H * 0.42} 180 ${H - 92} 100 ${H - 22}Z" fill="${c}"/><path d="M100 ${H - 14}V${H * 0.42}M100 ${H * 0.62}l34 -30M100 ${H * 0.72}l40 -34M100 ${H * 0.62}l-34 -30M100 ${H * 0.72}l-40 -34" stroke="${d}" stroke-width="2.4" fill="none"/>${titel(b.titel, 16, 44, a, { max: 25, bis: H * 0.36 - 8 })}${autorzeile(b.autor, 184, H - 10, a, "end")}`;

const schaltung: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${a}"/>${[0, 1, 2, 3, 4, 5, 6].map((i) => `<path d="M${-10 + i * 30} ${H}V${H - 60 - i * 12}l24 -26V${H * 0.4 - (i % 3) * 16}" fill="none" stroke="${c}" stroke-width="3"/><circle cx="${14 + i * 30}" cy="${H * 0.4 - (i % 3) * 16}" r="5" fill="${i % 2 ? d : c}"/>`).join("")}${titel(b.titel, 16, 42, "#fff", { schrift: GROTESK, f: 0.6, max: 25, bis: H * 0.4 - 44 })}<rect x="0" y="${H - 34}" width="200" height="34" fill="${d}"/>${autorzeile(b.autor, 16, H - 13, a)}`;

// --- Weitere Arten ---

/** Heft: Kopfband mit dem Titel, Ring, Jahr groß */
const heft: Muster = (b, [a, c, d]) =>
  `<rect width="200" height="${H}" fill="${c}"/><rect width="200" height="64" fill="${a}"/>${titel(b.titel, 16, 30, c, { schrift: GROTESK, f: 0.6, max: 21, n: 16, bis: 56 })}<circle cx="100" cy="${H * 0.58}" r="62" fill="none" stroke="${d}" stroke-width="13" stroke-dasharray="20 9"/><circle cx="100" cy="${H * 0.58}" r="24" fill="${a}"/>${jahrzahl(b.jahr, 184, H - 14, 24, d)}${autorzeile(b.autor, 16, H - 14, d, "start", b.jahr ? 100 : 168)}`;

/** Katalog: Kopfband, Raster aus Kacheln, Jahr groß */
const katalog: Muster = (b, [farbe, akzent, tinte]) => {
  const kacheln = Array.from({ length: 9 }, (_, i) => {
    const x = 18 + (i % 3) * 56;
    const y = 92 + Math.floor(i / 3) * 56;
    return `<rect x="${x}" y="${y}" width="50" height="50" rx="4" fill="${i % 4 === 0 ? akzent : "#fff"}" fill-opacity="${i % 4 === 0 ? 1 : 0.9}"/><circle cx="${x + 25}" cy="${y + 22}" r="${8 + ((i * 5) % 7)}" fill="${i % 4 === 0 ? "#fff" : farbe}" fill-opacity=".55"/><rect x="${x + 10}" y="${y + 38}" width="30" height="4" rx="2" fill="${tinte}" fill-opacity=".35"/>`;
  }).join("");
  return `<rect width="200" height="${H}" fill="${farbe}"/><rect width="200" height="74" fill="${tinte}"/>${titel(b.titel, 18, 32, "#fff", { schrift: GROTESK, w: 600, f: 0.58, abstand: 1.15, anker: "start", max: 19, breit: 164, n: 18, bis: 46 })}${klein(b.autor, 18, 60, akzent, "start", 164)}${kacheln}${jahrzahl(b.jahr, 182, H - 14, 30, tinte)}`;
};

/** Broschüre: drei Felder, gefaltet, schräges Band mit dem Titel */
const broschuere: Muster = (b, [grund, band, tinte]) => {
  const t = block(b.titel, 100, 0, "#fff", { breit: 150, hoehe: 40, max: 18 });
  return `<rect width="200" height="${H}" fill="${grund}"/><rect x="0" width="67" height="${H}" fill="#000" fill-opacity=".04"/><rect x="133" width="67" height="${H}" fill="#000" fill-opacity=".06"/><path d="M67 0V${H}M133 0V${H}" stroke="#000" stroke-opacity=".12"/><path d="M0 ${H * 0.58}L200 ${H * 0.4}V${H * 0.62}L0 ${H * 0.8}Z" fill="${band}"/><g transform="rotate(-15.1 100 ${H * 0.6})"><g transform="translate(0 ${(H * 0.6 - t.hoehe / 2).toFixed(1)})">${t.svg}</g></g><circle cx="100" cy="66" r="26" fill="none" stroke="${band}" stroke-width="5"/><circle cx="100" cy="66" r="10" fill="${tinte}"/>${klein(b.autor, 100, H - 22, tinte)}`;
};

/** Dokument als Aktenordner: flacher Rücken mit ringsum gleicher Pappkante, Schild und Griffloch, ohne Buchkanten (BF-70);
 * unter dem Titel Autor und Jahr */
const ordnerRuecken: Muster = (b, [farbe, schild, tinte]) => {
  const fasern = Array.from({ length: 40 }, (_, i) => `M${(i * 5.1).toFixed(1)} 0V${H}`).join("");
  const kante = `<rect x="2" y="2" width="196" height="${H - 4}" fill="none" stroke="#000" stroke-opacity=".24" stroke-width="4"/><rect x="5" y="5" width="190" height="${H - 10}" fill="none" stroke="#fff" stroke-opacity=".1"/>`;
  return `<rect width="200" height="${H}" fill="${farbe}"/><path d="${fasern}" stroke="#000" stroke-opacity=".06"/>${kante}<rect x="28" y="34" width="144" height="156" rx="3" fill="${schild}" stroke="#000" stroke-opacity=".18"/><rect x="33" y="39" width="134" height="146" rx="2" fill="none" stroke="${tinte}" stroke-opacity=".25"/>${block(b.titel, 100, 50, tinte, { breit: 118, hoehe: 96, max: 20 }).svg}<path d="M48 160H152" stroke="${tinte}" stroke-opacity=".3"/>${klein([b.autor, b.jahr].filter(Boolean).join(", "), 100, 176, tinte, "middle", 118)}<circle cx="100" cy="${H - 66}" r="21" fill="#000" fill-opacity=".55"/><circle cx="100" cy="${H - 66}" r="21" fill="none" stroke="#d5d9de" stroke-width="4"/><circle cx="100" cy="${H - 66}" r="17" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="2"/>`;
};

export const MUSTER = { typo, leinen, wellen, raster, teilung, kreis, sterne, globus, berge, blatt, schaltung, heft, katalog, broschuere, ordnerRuecken } satisfies Record<string, Muster>;

export type Mustername = keyof typeof MUSTER;
