import { readFile } from "node:fs/promises";
import path from "node:path";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import type { ReviewRecord, TabId, ViewMode } from "../lib/types";
import { ResultDesignPreview } from "./preview-client";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "审核结果设计预览 · 视鉴",
  robots: { index: false, follow: false },
};

export default async function DesignPreview({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  if (process.env.NODE_ENV !== "development") notFound();
  const records = JSON.parse(
    await readFile(
      path.join(
        process.cwd(),
        "..",
        "backend",
        "reports",
        "demo-showcase",
        "records.json",
      ),
      "utf8",
    ),
  ) as Record<string, ReviewRecord>;
  const cases = Object.entries(records).map(([id, record]) => ({
    id,
    title: record.video_name.replace(/^合成示例[｜|]\s*/, ""),
    result: record.result,
  }));
  const query = await searchParams;
  const selected = cases.some((item) => item.id === query.case)
    ? String(query.case)
    : cases[0].id;
  const tab: TabId = ["brief", "shots", "audit", "summary"].includes(
    String(query.tab),
  )
    ? (query.tab as TabId)
    : "brief";
  const view: ViewMode = query.view === "html" ? "html" : "structured";
  return (
    <ResultDesignPreview
      cases={cases}
      initialCase={selected}
      initialTab={tab}
      initialView={view}
    />
  );
}
