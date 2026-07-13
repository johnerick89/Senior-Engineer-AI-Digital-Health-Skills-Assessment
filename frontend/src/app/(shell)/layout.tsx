"use client";

import dynamic from "next/dynamic";

const RagAppLayout = dynamic(() => import("@/components/RagAppLayout"), {
  ssr: false,
});

export default function ShellLayout() {
  return <RagAppLayout />;
}
