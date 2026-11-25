// Ein Strom aus JSON-Zeilen, Stück für Stück

export async function* zeilenAus<T>(koerper: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const leser = koerper.getReader();
  const schrift = new TextDecoder();
  let rest = "";
  try {
    for (;;) {
      const { value, done } = await leser.read();
      rest += done ? schrift.decode() : schrift.decode(value, { stream: true });
      const zeilen = rest.split("\n");
      rest = done ? "" : (zeilen.pop() ?? "");
      for (const z of zeilen) if (z.trim()) yield JSON.parse(z) as T;
      if (done) return;
    }
  } finally {
    void leser.cancel().catch(() => undefined);
  }
}
