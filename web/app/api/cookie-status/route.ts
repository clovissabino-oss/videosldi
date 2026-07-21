import { NextResponse } from "next/server";
import { criarClienteServidor } from "../../../lib/supabase/servidor";

export const dynamic = "force-dynamic";

// Status do cookie do LDI (publicado pelo worker) — para banners de aviso.
// Nunca lê config_ldi (o cookie em si não sai do service_role).
export async function GET() {
  const supabase = await criarClienteServidor();
  try {
    const { data, error } = await supabase
      .from("cookie_status")
      .select("*")
      .eq("id", 1)
      .maybeSingle();
    if (error) throw new Error(error.message);
    return NextResponse.json({ data });
  } catch (e) {
    const erro = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ data: null, erro }, { status: 500 });
  }
}
