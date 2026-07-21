import { NextResponse } from "next/server";
import { criarClienteServidor } from "../../../lib/supabase/servidor";
import { listarFila } from "../../../lib/coleta";

export const dynamic = "force-dynamic";

// Fila de coleta (para o polling da tela /coleta) — RLS SELECT authenticated
// já cobre; sem gate extra de papel aqui (é só leitura, o middleware já
// exige sessão).
export async function GET() {
  try {
    const supabase = await criarClienteServidor();
    const data = await listarFila(supabase);
    return NextResponse.json({ data });
  } catch (e) {
    const erro = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ data: null, erro }, { status: 500 });
  }
}
