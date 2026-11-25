// Die Schnittstelle der KI liegt unter /v1; die Suche im Netz findet nur den Rechner
export function kiAdresse(eingabe: string): string {
  const roh = eingabe.trim().replace(/\/+$/, "");
  if (!roh) return "";
  const mitProtokoll = /^https?:\/\//i.test(roh) ? roh : `http://${roh}`;
  return /\/v\d+$/.test(mitProtokoll) ? mitProtokoll : `${mitProtokoll}/v1`;
}
