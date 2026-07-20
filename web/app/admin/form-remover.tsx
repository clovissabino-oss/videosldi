"use client";

import { removerUsuario } from "./actions";

export function FormRemover({
  id, email, desabilitado,
}: {
  id: string; email: string; desabilitado: boolean;
}) {
  return (
    <form
      action={removerUsuario}
      onSubmit={(e) => {
        if (!confirm(`Remover o acesso de ${email}?`)) e.preventDefault();
      }}
      style={{ display: "inline" }}
    >
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="email" value={email} />
      <button
        type="submit"
        disabled={desabilitado}
        title={desabilitado ? "Você não pode remover a si mesmo" : undefined}
        style={{
          font: "inherit", fontSize: 12.5, cursor: desabilitado ? "not-allowed" : "pointer",
          background: "transparent", color: desabilitado ? "#8a897f" : "#b23230",
          border: "1px solid currentColor", borderRadius: 6, padding: "3px 10px",
        }}
      >
        Remover
      </button>
    </form>
  );
}
