import "@testing-library/jest-dom";

// jsdom does not provide fetch; components under test call it.
if (typeof globalThis.fetch !== "function") {
  globalThis.fetch = jest.fn() as typeof fetch;
}
