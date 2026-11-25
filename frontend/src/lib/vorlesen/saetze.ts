// Text in Sätze teilen; überlange an Wortgrenzen

const HOECHSTENS = 220;

export function saetze(text: string): string[] {
  const aus: string[] = [];
  for (let satz of text.replace(/\s+/g, " ").split(/(?<=[.!?:;])\s+/)) {
    while (satz.length > HOECHSTENS) {
      const schnitt = satz.lastIndexOf(" ", HOECHSTENS);
      aus.push(satz.slice(0, schnitt > 0 ? schnitt : HOECHSTENS).trim());
      satz = satz.slice(schnitt > 0 ? schnitt : HOECHSTENS).trim();
    }
    if (satz.trim()) aus.push(satz.trim());
  }
  return aus;
}
