import { readFile } from "fs/promises";
import { NextResponse } from "next/server";
import path from "path";

export const dynamic = "force-dynamic";

// GET /avaliacao — a tela busca tudo em /api/... depois de carregar.
export async function GET() {
  const html = await readFile(
    path.join(process.cwd(), "telas", "avaliacao.html"), "utf-8"
  );
  return new NextResponse(html, {
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}
