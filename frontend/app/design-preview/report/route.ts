import { readFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-dynamic";
const CASES = new Set([
  "rooftop_parkour",
  "rooftop_warning",
  "cross_event_link",
  "id_card_screen",
  "puppy_vlog",
]);

export async function GET(request: Request) {
  if (process.env.NODE_ENV !== "development")
    return new Response("Not found", { status: 404 });
  const id = new URL(request.url).searchParams.get("case");
  if (!id || !CASES.has(id)) return new Response("Not found", { status: 404 });
  const content = await readFile(
    path.join(
      process.cwd(),
      "..",
      "backend",
      "reports",
      "demo-showcase",
      `${id}.html`,
    ),
    "utf8",
  );
  return new Response(content, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex",
    },
  });
}
