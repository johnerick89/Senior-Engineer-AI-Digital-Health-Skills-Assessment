"use client";

import { ChainlitAPI, ChainlitContext } from "@chainlit/react-client";
import { RecoilRoot } from "recoil";

import { clientConfig } from "@/config/client";

const apiClient = new ChainlitAPI(clientConfig.chainlitUrl, "webapp");

export default function ChainlitProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ChainlitContext.Provider value={apiClient}>
      <RecoilRoot>{children}</RecoilRoot>
    </ChainlitContext.Provider>
  );
}
