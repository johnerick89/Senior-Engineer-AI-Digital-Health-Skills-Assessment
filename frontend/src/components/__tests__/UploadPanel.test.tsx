import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UploadPanel from "@/components/UploadPanel";
import { clientConfig } from "@/config/client";

function mockFetch(impl: typeof fetch): jest.Mock {
  const fetchMock = jest.fn(impl) as unknown as jest.Mock;
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

describe("UploadPanel", () => {
  beforeEach(() => {
    jest.restoreAllMocks();
    window.confirm = jest.fn(() => true);
  });

  it("loads documents from GET /api/v1/documents on mount", async () => {
    const fetchMock = mockFetch(async () =>
      ({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "doc-1",
            filename: "training_manual.pdf",
            status: "ready",
            size_kb: 2380,
            chunk_count: 47,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: null,
          },
        ],
      }) as Response,
    );

    render(<UploadPanel />);

    expect(await screen.findByText("training_manual.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Ready/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      `${clientConfig.apiV1Url}/documents`,
    );
  });

  it("shows empty state when the list is empty", async () => {
    mockFetch(async () =>
      ({
        ok: true,
        status: 200,
        json: async () => [],
      }) as Response,
    );

    render(<UploadPanel />);

    expect(
      await screen.findByText("No documents uploaded yet."),
    ).toBeInTheDocument();
  });

  it("calls DELETE /api/v1/documents/{id} when remove is confirmed", async () => {
    const user = userEvent.setup();
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "doc-1",
            filename: "training_manual.pdf",
            status: "ready",
            size_kb: 10,
            chunk_count: 1,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: null,
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: async () => ({}),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UploadPanel />);
    expect(await screen.findByText("training_manual.pdf")).toBeInTheDocument();

    const row = screen.getByText("training_manual.pdf").closest("div")
      ?.parentElement?.parentElement as HTMLElement;
    await user.click(
      within(row).getByRole("button", { name: /Remove training_manual.pdf/i }),
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `${clientConfig.apiV1Url}/documents/doc-1`,
        { method: "DELETE" },
      );
    });
    await waitFor(() => {
      expect(screen.queryByText("training_manual.pdf")).not.toBeInTheDocument();
    });
  });
});
