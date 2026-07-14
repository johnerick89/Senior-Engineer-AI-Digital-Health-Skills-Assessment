export default function AssignmentPanel() {
  return (
    <div className="h-full overflow-y-auto">
      <article className="mx-auto w-full max-w-3xl px-4 py-6 md:px-8 md:py-10">
        <header className="mb-8 border-b-2 border-[#c8102e] pb-4">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-[1.6rem]">
            Last Mile Health — Senior Full-Stack Engineer, AI & Digital Health
            Practice Assessment
          </h1>
          <p className="mt-2 text-sm text-slate-500 md:text-[0.95rem]">
            Thank you for taking the time to complete this assessment. Please
            read the requirements carefully before you begin.
          </p>
        </header>

        <Section title="Project Overview">
          <p className="text-sm leading-relaxed text-slate-700">
            You are tasked with building a{" "}
            <strong>Retrieval-Augmented Generation (RAG)</strong> application
            using the provided starter code. Your solution should demonstrate
            production-quality thinking across the full stack.
          </p>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border border-slate-200 px-3 py-2 font-semibold">
                    Layer
                  </th>
                  <th className="border border-slate-200 px-3 py-2 font-semibold">
                    Provided Starter
                  </th>
                  <th className="border border-slate-200 px-3 py-2 font-semibold">
                    URL
                  </th>
                  <th className="border border-slate-200 px-3 py-2 font-semibold">
                    Substitution Policy
                  </th>
                </tr>
              </thead>
              <tbody className="text-slate-700">
                <tr>
                  <td className="border border-slate-200 px-3 py-2">Frontend</td>
                  <td className="border border-slate-200 px-3 py-2">
                    Next.js (React)
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    <a
                      href="http://localhost:3000"
                      className="text-teal-700 underline hover:text-teal-800"
                    >
                      localhost:3000
                    </a>
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    Any framework you prefer.
                  </td>
                </tr>
                <tr>
                  <td className="border border-slate-200 px-3 py-2">Chat UI</td>
                  <td className="border border-slate-200 px-3 py-2">Chainlit</td>
                  <td className="border border-slate-200 px-3 py-2">
                    <a
                      href="http://localhost:8000"
                      className="text-teal-700 underline hover:text-teal-800"
                    >
                      localhost:8000
                    </a>
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    May be used in place of or alongside the Next.js frontend
                    for the chat interface.
                  </td>
                </tr>
                <tr>
                  <td className="border border-slate-200 px-3 py-2">Backend</td>
                  <td className="border border-slate-200 px-3 py-2">
                    FastAPI (Python)
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    <a
                      href="http://localhost:6100"
                      className="text-teal-700 underline hover:text-teal-800"
                    >
                      localhost:6100
                    </a>
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    Substitute with a framework you are more comfortable with,
                    provided core requirements are met.
                  </td>
                </tr>
                <tr>
                  <td className="border border-slate-200 px-3 py-2">Database</td>
                  <td className="border border-slate-200 px-3 py-2">
                    PostgreSQL + pgvector
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                      localhost:5432
                    </code>
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    Required; do not substitute.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Requirements">
          <Requirement
            number={1}
            title="Chat Interface"
            items={[
              "A user-friendly chat UI for interacting with the RAG system.",
              "Responses should be grounded in the content of uploaded documents.",
            ]}
          />
          <Requirement
            number={2}
            title="PDF Upload"
            items={[
              "A dedicated page on the frontend for allowing users to upload PDF documents for ingestion into the RAG pipeline.",
            ]}
          />
          <Requirement
            number={3}
            title="RAG Backend"
            items={[
              "Implement a backend service that handles document ingestion, vector storage, and retrieval-augmented generation.",
              "Ensure the backend is scalable, secure, and well-documented.",
            ]}
          />
          <Requirement
            number={4}
            title="Database"
            items={[
              "Use PostgreSQL with pgvector for vector storage.",
              "The database has not been pre-configured; you will need to set up the necessary tables and indexes for efficient RAG operations.",
            ]}
          />
          <Requirement
            number={5}
            title="Testing"
            items={[
              "Implement automated tests for the backend and frontend to ensure functionality and reliability.",
              "Instructions for running tests should be included in your README.",
            ]}
          />
          <Requirement
            number={6}
            title="Local Run Instructions"
            items={[
              "Clear, step-by-step instructions for running the application locally, included in your README.",
            ]}
          />
          <Requirement
            number={7}
            title="Production Deployment Plan"
            items={[
              "A brief written outline of how you would deploy this application to production, covering cloud provider choice, CI/CD strategy, and any infrastructure considerations.",
            ]}
          />
        </Section>

        <div className="mt-8 rounded-lg border-l-4 border-amber-400 bg-amber-50 px-4 py-4 md:px-5">
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-amber-800">
            Bonus
          </h2>
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
            <li>
              Include a .env.example file with all necessary environment
              variables in case you use a .env file.
            </li>
            <li>
              Document architectural decisions and any notable trade-offs.
            </li>
            <li>
              Include additional service layers (e.g., caching, scheduling) if
              you believe they would enhance the solution, and document your
              reasoning.
            </li>
          </ul>
        </div>

        <hr className="my-8 border-slate-200" />

        <Section title="Additional Notes">
          <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
            <li>
              Feel free to expand your README or inline documentation as you
              progress through the assessment.
            </li>
            <li>
              If you make architectural changes from the starter code, document
              your reasoning clearly.
            </li>
            <li>
              Commit frequently with descriptive messages to illustrate your
              development workflow; avoid submitting a single, monolithic commit
              at the conclusion of the assessment.
            </li>
          </ul>
        </Section>

        <p className="mt-8 text-base font-bold text-slate-900">
          Good luck — we look forward to reviewing your submission!
        </p>
      </article>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-[#c8102e]">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Requirement({
  number,
  title,
  items,
}: {
  number: number;
  title: string;
  items: string[];
}) {
  return (
    <div className="mt-5">
      <h3 className="mb-1 text-sm font-bold text-slate-900">
        {number}. {title}
      </h3>
      <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
