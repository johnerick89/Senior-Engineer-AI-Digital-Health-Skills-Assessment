"use client";

import { useEffect, useState } from "react";

const BACKEND_URL = "http://localhost:6100";

export default function AssignmentPanel() {
  const [html, setHtml] = useState("Loading...");

  useEffect(() => {
    fetch(`${BACKEND_URL}/assignment`, { headers: { Accept: "text/html" } })
      .then((res) => res.text())
      .then((data) => setHtml(data))
      .catch(() => setHtml("Failed to load assignment brief."));
  }, []);

  return (
    <div className="fastapi-html mx-auto w-full max-w-4xl overflow-y-auto p-4 md:p-8">
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
