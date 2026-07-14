"use client";

import dynamic from "next/dynamic";

const RagAppShell = dynamic(() => import("@/components/RagAppShell"), {
  ssr: false,
});

export default function RagAppLayout() {
  return <RagAppShell />;
}
