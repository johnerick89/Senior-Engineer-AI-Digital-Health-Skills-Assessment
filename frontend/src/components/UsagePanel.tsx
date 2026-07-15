import { useEffect, useState } from "react";
import { clientConfig } from "@/config/client";

type UsageBucket = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
};

type UsageSummary = {
  chats: UsageBucket;
  suggestions: UsageBucket;
  embeddings: UsageBucket;
  total_tokens: number;
  estimated_cost_usd: number;
};

function formatUsd(amount: number): string {
  if (amount <= 0) return "$0.00";
  if (amount < 0.01) return `$${amount.toFixed(6)}`;
  return `$${amount.toFixed(4)}`;
}

function BucketCard({
  title,
  description,
  bucket,
}: {
  title: string;
  description: string;
  bucket: UsageBucket;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <p className="mt-1 text-xs text-slate-500">{description}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-slate-400">Prompt tokens</dt>
          <dd className="font-medium text-slate-800">
            {bucket.prompt_tokens.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Completion tokens</dt>
          <dd className="font-medium text-slate-800">
            {bucket.completion_tokens.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Total tokens</dt>
          <dd className="font-medium text-slate-800">
            {bucket.total_tokens.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Est. cost</dt>
          <dd className="font-medium text-teal-800">
            {formatUsd(bucket.estimated_cost_usd)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

export default function UsagePanel() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`${clientConfig.apiV1Url}/usage`);
        if (!response.ok) {
          throw new Error(`Failed to load usage (${response.status})`);
        }
        const data = (await response.json()) as UsageSummary;
        if (!cancelled) setSummary(data);
      } catch {
        if (!cancelled) {
          setError("Could not load usage summary.");
          setSummary(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="h-full overflow-y-auto p-4 md:p-8">
      <div className="mx-auto w-full max-w-3xl">
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-slate-900">Usage</h1>
          <p className="mt-1 text-sm text-slate-500">
            Estimated token usage and USD list-price cost across chats,
            suggestions, and document embeddings.
          </p>
        </header>

        {loading && (
          <p className="text-sm text-slate-400">Loading usage…</p>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && summary && (
          <div className="space-y-4">
            <div className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-900">
              <span className="font-medium">All time:</span>{" "}
              {summary.total_tokens.toLocaleString()} tokens ·{" "}
              {formatUsd(summary.estimated_cost_usd)}
            </div>

            <BucketCard
              title="Chats"
              description="Query embeddings (prompts) plus assistant completions."
              bucket={summary.chats}
            />
            <BucketCard
              title="Suggestions"
              description="Starter topic generation for new chats."
              bucket={summary.suggestions}
            />
            <BucketCard
              title="Embeddings"
              description="Document chunk embeddings created during upload/ingest."
              bucket={summary.embeddings}
            />
          </div>
        )}
      </div>
    </div>
  );
}
