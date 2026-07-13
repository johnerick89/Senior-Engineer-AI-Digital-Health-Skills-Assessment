"use client";

import ChainlitProvider from "@/components/providers/ChainlitProvider";
import RagAppShell from "@/components/RagAppShell";

export default function RagAppLayout() {
  return (
    <ChainlitProvider>
      <RagAppShell />
    </ChainlitProvider>
  );
}
