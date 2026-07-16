import { render, screen } from "@testing-library/react";
import UsagePanel from "@/components/UsagePanel";
import { clientConfig } from "@/config/client";

describe("UsagePanel", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
  });

  it("fetches GET /api/v1/usage and renders totals", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        chats: {
          prompt_tokens: 10,
          completion_tokens: 20,
          total_tokens: 30,
          estimated_cost_usd: 0.01,
        },
        suggestions: {
          prompt_tokens: 1,
          completion_tokens: 2,
          total_tokens: 3,
          estimated_cost_usd: 0.001,
        },
        embeddings: {
          prompt_tokens: 5,
          completion_tokens: 0,
          total_tokens: 5,
          estimated_cost_usd: 0.002,
        },
        total_tokens: 38,
        estimated_cost_usd: 0.013,
      }),
    } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UsagePanel />);

    expect(await screen.findByText(/38 tokens/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(`${clientConfig.apiV1Url}/usage`);
  });

  it("shows an error when the usage request is not ok", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response) as unknown as typeof fetch;

    render(<UsagePanel />);

    expect(
      await screen.findByText("Could not load usage summary."),
    ).toBeInTheDocument();
  });

  it("shows an error when fetch throws", async () => {
    globalThis.fetch = jest
      .fn()
      .mockRejectedValue(new Error("offline")) as unknown as typeof fetch;

    render(<UsagePanel />);

    expect(
      await screen.findByText("Could not load usage summary."),
    ).toBeInTheDocument();
  });
});
