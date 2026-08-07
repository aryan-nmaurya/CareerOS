import { BASE_URL } from "@/services/api/client";

export interface SseEvent<T = unknown> {
  event: string;
  data: T;
}

function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}

/**
 * fetch + ReadableStream SSE reader. Not EventSource, which can't POST.
 * Scans the accumulated buffer for `\n\n` block boundaries rather than
 * assuming a boundary lands inside a single read() chunk — chunk
 * boundaries are a transport detail with no relation to SSE framing,
 * exactly like the backend's own raw-text chunking.
 */
export async function* sseFetch(path: string, init?: RequestInit): AsyncGenerator<SseEvent> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseSseBlock(block);
      if (event) yield event;
      boundary = buffer.indexOf("\n\n");
    }
  }
}
