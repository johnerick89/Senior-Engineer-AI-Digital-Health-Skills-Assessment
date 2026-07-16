import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UploadPanel from "@/components/UploadPanel";
import { clientConfig } from "@/config/client";

function mockFetch(impl: typeof fetch): jest.Mock {
  const fetchMock = jest.fn(impl) as unknown as jest.Mock;
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

function pdfFile(name: string, sizeBytes = 2048): File {
  const content = new Uint8Array(Math.max(sizeBytes, 4));
  content[0] = 0x25;
  content[1] = 0x50;
  content[2] = 0x44;
  content[3] = 0x46;
  return new File([content], name, { type: "application/pdf" });
}

function textFile(name: string): File {
  return new File(["hello"], name, { type: "text/plain" });
}

function ndjsonBody(lines: string[]) {
  const encoder = new TextEncoder();
  const chunks = lines.map((line) => encoder.encode(`${line}\n`));
  let index = 0;
  return {
    getReader() {
      return {
        async read() {
          if (index >= chunks.length) {
            return { done: true as const, value: undefined };
          }
          const value = chunks[index];
          index += 1;
          return { done: false as const, value };
        },
      };
    },
  };
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

  it("shows load error when document list fetch fails", async () => {
    mockFetch(async () => {
      throw new Error("network");
    });

    render(<UploadPanel />);

    expect(
      await screen.findByText("Could not load ingested documents."),
    ).toBeInTheDocument();
  });

  it("rejects non-PDF files before uploading", async () => {
    mockFetch(async () =>
      ({
        ok: true,
        status: 200,
        json: async () => [],
      }) as Response,
    );

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [textFile("notes.txt")] } });

    expect(
      await screen.findByText(/Only PDF files are supported/i),
    ).toBeInTheDocument();
  });

  it("rejects oversized PDFs before uploading", async () => {
    mockFetch(async () =>
      ({
        ok: true,
        status: 200,
        json: async () => [],
      }) as Response,
    );

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");

    const big = pdfFile("huge.pdf", 21 * 1024 * 1024);
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [big] } });

    expect(
      await screen.findByText(/File exceeds 20MB limit/i),
    ).toBeInTheDocument();
  });

  it("uploads a PDF via NDJSON stream and refreshes the list", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: ndjsonBody([
          JSON.stringify({
            filename: "guide.pdf",
            document_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            status: "ready",
            chunk_count: 3,
            error: null,
          }),
        ]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            filename: "guide.pdf",
            status: "ready",
            size_kb: 2,
            chunk_count: 3,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: null,
          },
        ],
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [pdfFile("guide.pdf")] } });

    expect(await screen.findByText("guide.pdf")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `${clientConfig.apiV1Url}/documents`,
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("marks uploads failed when POST returns an error body", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Only PDF files are supported." }),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [pdfFile("guide.pdf")] } });

    expect(
      await screen.findByText("Only PDF files are supported."),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Failed/i)).toBeInTheDocument();
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

  it("does not delete when confirm is cancelled", async () => {
    window.confirm = jest.fn(() => false);
    const user = userEvent.setup();
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        {
          id: "doc-1",
          filename: "keep.pdf",
          status: "ready",
          size_kb: 1,
          chunk_count: 1,
          uploaded_at: "2026-07-13T10:22:00Z",
          error_message: null,
        },
      ],
    } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UploadPanel />);
    expect(await screen.findByText("keep.pdf")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /Remove keep.pdf/i }),
    );
    expect(screen.getByText("keep.pdf")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("surfaces delete failures", async () => {
    const user = userEvent.setup();
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "doc-1",
            filename: "bad-delete.pdf",
            status: "failed",
            size_kb: 1,
            chunk_count: 0,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: "embed failed",
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({}),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UploadPanel />);
    expect(await screen.findByText("bad-delete.pdf")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Remove bad-delete.pdf/i }),
    );
    expect(
      await screen.findByText("Could not delete document."),
    ).toBeInTheDocument();
  });

  it("handles drag-and-drop onto the drop zone", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: ndjsonBody([
          JSON.stringify({
            filename: "dropped.pdf",
            document_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            status: "ready",
            chunk_count: 1,
            error: null,
          }),
        ]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            filename: "dropped.pdf",
            status: "ready",
            size_kb: 1,
            chunk_count: 1,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: null,
          },
        ],
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");

    const dropZone = screen.getByText(/Drag and drop PDFs here/i).closest("div");
    expect(dropZone).toBeTruthy();
    fireEvent.dragOver(dropZone as HTMLElement);
    fireEvent.drop(dropZone as HTMLElement, {
      dataTransfer: { files: [pdfFile("dropped.pdf")] },
    });

    expect(await screen.findByText("dropped.pdf")).toBeInTheDocument();
  });

  it("removes a pending upload id without calling DELETE", async () => {
    const user = userEvent.setup();
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("not json");
        },
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [pdfFile("pending.pdf")] } });

    expect(await screen.findByText("pending.pdf")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /Remove pending.pdf/i }),
    );
    await waitFor(() => {
      expect(screen.queryByText("pending.pdf")).not.toBeInTheDocument();
    });
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === "DELETE")).toBe(
      false,
    );
  });

  it("removes row on DELETE 404", async () => {
    const user = userEvent.setup();
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [
          {
            id: "gone",
            filename: "gone.pdf",
            status: "ready",
            size_kb: 1,
            chunk_count: 1,
            uploaded_at: "2026-07-13T10:22:00Z",
            error_message: null,
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Document not found" }),
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    render(<UploadPanel />);
    expect(await screen.findByText("gone.pdf")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Remove gone.pdf/i }));
    await waitFor(() => {
      expect(screen.queryByText("gone.pdf")).not.toBeInTheDocument();
    });
  });

  it("fails when the upload response has no body stream", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        body: null,
      } as Response);
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [pdfFile("nostream.pdf")] } });

    expect(
      await screen.findByText("No response stream available"),
    ).toBeInTheDocument();
  });

  it("parses a trailing NDJSON line left in the buffer", async () => {
    const encoder = new TextEncoder();
    const payload = JSON.stringify({
      filename: "tail.pdf",
      document_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
      status: "ready",
      chunk_count: 1,
      error: null,
    });
    const body = {
      getReader() {
        let done = false;
        return {
          async read() {
            if (done) return { done: true as const, value: undefined };
            done = true;
            // No trailing newline — exercises buffer.trim() branch
            return { done: false as const, value: encoder.encode(payload) };
          },
        };
      },
    };
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        body,
      } as Response)
      .mockRejectedValueOnce(new Error("refetch failed"));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<UploadPanel />);
    await screen.findByText("No documents uploaded yet.");
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [pdfFile("tail.pdf")] } });

    expect(await screen.findByText("tail.pdf")).toBeInTheDocument();
  });
});
