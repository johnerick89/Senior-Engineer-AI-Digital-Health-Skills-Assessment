import "@testing-library/jest-dom";
import { TextEncoder, TextDecoder } from "util";

// jsdom does not provide fetch; components under test call it.
if (typeof globalThis.fetch !== "function") {
  globalThis.fetch = jest.fn() as typeof fetch;
}

// ReadableStream NDJSON helpers need TextEncoder/Decoder in Jest.
Object.assign(globalThis, { TextEncoder, TextDecoder });
