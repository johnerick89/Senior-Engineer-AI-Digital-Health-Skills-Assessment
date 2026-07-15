import { clientConfig } from "@/config/client";

describe("clientConfig", () => {
  it("exposes a versioned apiV1Url under the backend host", () => {
    expect(clientConfig.apiV1Url).toBe(
      `${clientConfig.backendUrl.replace(/\/$/, "")}/api/v1`,
    );
    expect(clientConfig.apiV1Url.endsWith("/api/v1")).toBe(true);
  });

  it("defaults to localhost:6100 when env is unset", () => {
    expect(clientConfig.backendUrl).toMatch(/localhost:6100|backend:6100/);
  });
});
