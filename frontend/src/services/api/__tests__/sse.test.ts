import { afterEach, describe, expect, it, vi } from "vitest";

import { sseFetch } from "@/services/api/sse";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchReturning(chunks: string[]) {
  return vi.fn(async () => new Response(streamFromChunks(chunks), { status: 200 }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function collect(path: string) {
  const events = [];
  for await (const event of sseFetch(path)) events.push(event);
  return events;
}

describe("sseFetch", () => {
  it("parses a single complete event", async () => {
    vi.stubGlobal("fetch", mockFetchReturning(['event: meta\ndata: {"title":"T"}\n\n']));

    expect(await collect("/x")).toEqual([{ event: "meta", data: { title: "T" } }]);
  });

  it("reassembles an event split across multiple read chunks", async () => {
    vi.stubGlobal("fetch", mockFetchReturning(['event: meta\ndata: {"tit', 'le":"T"}\n\n']));

    expect(await collect("/x")).toEqual([{ event: "meta", data: { title: "T" } }]);
  });

  it("emits multiple events in arrival order, one per block", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetchReturning([
        'event: meta\ndata: {"a":1}\n\n',
        'event: phase\ndata: {"b":2}\n\nevent: done\ndata: {"c":3}\n\n',
      ]),
    );

    const events = await collect("/x");
    expect(events.map((e) => e.event)).toEqual(["meta", "phase", "done"]);
    expect(events.map((e) => e.data)).toEqual([{ a: 1 }, { b: 2 }, { c: 3 }]);
  });
});
