import type { AppProps } from "next/app";
import Head from "next/head";
import RagAppShell from "@/components/RagAppShell";
import "@/styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>Senior Full-Stack Engineer, AI & Digital Health</title>
        <meta
          name="description"
          content="Practice interview for senior full-stack engineer role at Last Mile Health."
        />
      </Head>
      <RagAppShell>
        <Component {...pageProps} />
      </RagAppShell>
    </>
  );
}
