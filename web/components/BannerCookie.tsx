import { criarClienteServidor } from "../lib/supabase/servidor";

interface StatusCookie {
  dias_restantes: number | null;
  valido: boolean;
}

// Aviso de status do cookie do LDI (publicado por cookie_status, id=1).
// Nunca lê config_ldi — só os campos derivados que o worker publica.
export async function BannerCookie() {
  const supabase = await criarClienteServidor();
  const { data: status } = await supabase
    .from("cookie_status")
    .select("dias_restantes, valido")
    .eq("id", 1)
    .maybeSingle<StatusCookie>();

  if (!status) return null;

  if (!status.valido) {
    return (
      <p
        style={{
          fontSize: 13, margin: "0 0 16px", padding: "9px 13px",
          borderRadius: 8, background: "#fbe9e8", color: "#c0392b",
          border: "1px solid #f0c4c1",
        }}
      >
        🍪 Cookie do LDI vencido — coletas estão paradas. Avise um administrador.
      </p>
    );
  }

  if (status.dias_restantes != null && status.dias_restantes <= 3) {
    return (
      <p
        style={{
          fontSize: 13, margin: "0 0 16px", padding: "9px 13px",
          borderRadius: 8, background: "#fdf3dc", color: "#b9770e",
          border: "1px solid #eeddb0",
        }}
      >
        🍪 Cookie do LDI vence em {Math.round(status.dias_restantes)} dia(s) — renove no /admin.
      </p>
    );
  }

  return null;
}
