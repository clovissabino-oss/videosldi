import { listarUsuarios, criarClienteAdmin } from "../../lib/supabase/admin";
import { exigirAdmin } from "../../lib/papeis";
import { convidarUsuario } from "./actions";
import { FormRemover } from "./form-remover";
import { FormPapel } from "./form-papel";

export const dynamic = "force-dynamic";

const MENSAGENS: Record<string, (email?: string) => string> = {
  email: () => "Informe um e-mail válido.",
  dominio: () => "ℹ Esse e-mail é @estrategia.com — entra direto pelo login, sem convite.",
  erro: () => "❌ Não foi possível concluir — tente de novo.",
  proprio: () => "⚠ Você não pode remover a si mesmo.",
  "proprio-papel": () => "⚠ Você não pode alterar o próprio papel.",
  convidado: (e) => `✅ Convite enviado para ${e ?? "o e-mail"}.`,
  removido: (e) => `✅ Acesso de ${e ?? "usuário"} removido.`,
  "papel-definido": (e) => `✅ Papel de ${e ?? "usuário"} atualizado.`,
};

// Data local do projeto: pt-BR com fuso explícito (servidor do Vercel é UTC).
const dataLocal = (iso: string | undefined) =>
  iso
    ? new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit", month: "2-digit", year: "2-digit",
        hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo",
      })
    : "—";

export default async function PaginaAdmin({
  searchParams,
}: {
  searchParams: Promise<{ msg?: string; email?: string }>;
}) {
  const { msg, email } = await searchParams;

  const user = await exigirAdmin("notFound");

  const admin = criarClienteAdmin();
  const usuarios = await listarUsuarios(admin);
  usuarios.sort((a, b) => (a.email ?? "").localeCompare(b.email ?? "", "pt-BR"));

  return (
    <main
      style={{
        maxWidth: 760, margin: "0 auto", padding: "32px 24px 64px",
        background: "#fcfcfb", color: "#0b0b0b", minHeight: "100vh",
        font: '14.5px/1.5 "Segoe UI", system-ui, sans-serif',
      }}
    >
      <p style={{
        fontSize: 11, letterSpacing: ".14em", textTransform: "uppercase",
        color: "#2a78d6", fontWeight: 600, margin: "0 0 6px",
      }}>
        <a href="/" style={{ color: "#8a897f", textDecoration: "none" }}>← painel</a>
        {" "}Painel de Conteúdo · administração de acesso
      </p>
      <h1 style={{ fontSize: 21, fontWeight: 650, margin: "0 0 4px" }}>Usuários</h1>
      <p style={{ color: "#52514e", fontSize: 13, margin: "0 0 16px" }}>
        @estrategia.com entra sozinho pelo login. Convide aqui apenas e-mails externos.
      </p>

      {msg && MENSAGENS[msg] && (
        <p style={{ fontSize: 13, margin: "0 0 12px" }}>{MENSAGENS[msg](email)}</p>
      )}

      <form action={convidarUsuario} style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input
          type="email" name="email" required placeholder="externo@dominio.com"
          style={{
            flex: 1, font: "inherit", padding: "8px 11px",
            border: "1px solid #e3e2dd", borderRadius: 8,
          }}
        />
        <button
          type="submit"
          style={{
            font: "inherit", fontWeight: 600, cursor: "pointer",
            background: "#2a78d6", color: "#fff", border: 0, borderRadius: 8,
            padding: "8px 16px",
          }}
        >
          Convidar
        </button>
      </form>

      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
        <thead>
          <tr>
            {["E-mail", "Papel", "Confirmado", "Último login", ""].map((t) => (
              <th key={t} style={{
                textAlign: "left", padding: "8px 10px", color: "#52514e",
                fontSize: 11, letterSpacing: ".07em", textTransform: "uppercase",
                borderBottom: "1px solid #e3e2dd",
              }}>{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {usuarios.map((u) => (
            <tr key={u.id}>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {u.email}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                <FormPapel
                  id={u.id}
                  email={u.email ?? ""}
                  papel={String(u.app_metadata?.role ?? "")}
                  desabilitado={u.id === user.id}
                />
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {u.email_confirmed_at ? "✅" : "📨 pendente"}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                {dataLocal(u.last_sign_in_at)}
              </td>
              <td style={{ padding: "8px 10px", borderBottom: "1px solid #e3e2dd" }}>
                <FormRemover id={u.id} email={u.email ?? ""} desabilitado={u.id === user.id} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
