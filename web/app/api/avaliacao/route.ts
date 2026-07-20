import { NextResponse } from "next/server";
import { snapshotAtual } from "../../../lib/dados";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

export const dynamic = "force-dynamic";

// Devolve o payload PRONTO de painel.dados_avaliacao() gravado pelo sync —
// mesmo {data: ...} que a tela local consome do Flask.
export async function GET(request: Request) {
  const cursoId = new URL(request.url).searchParams.get("curso_id") ?? "";
  const supabase = await criarClienteServidor();
  let snap;
  try {
    snap = await snapshotAtual(supabase);
  } catch (e) {
    const erro = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ data: null, erro }, { status: 500 });
  }
  if (!snap) return NextResponse.json({ data: null });

  const { data, error } = await supabase
    .from("avaliacao_curso")
    .select("payload")
    .eq("snapshot_id", snap.id)
    .eq("curso_id", cursoId)
    .maybeSingle();
  if (error) {
    return NextResponse.json({ data: null, erro: error.message }, { status: 500 });
  }
  return NextResponse.json({ data: data?.payload ?? null });
}
