"use client";

import { definirPapel } from "./actions";

export function FormPapel({
  id, email, papel, desabilitado,
}: {
  id: string; email: string; papel: string; desabilitado: boolean;
}) {
  return (
    <form
      action={definirPapel}
      onSubmit={(e) => {
        const novoPapel = new FormData(e.currentTarget).get("papel");
        if (!confirm(`Definir o papel de ${email} como "${novoPapel || "—"}"?`)) {
          e.preventDefault();
        }
      }}
    >
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="email" value={email} />
      <select
        name="papel"
        defaultValue={papel}
        disabled={desabilitado}
        title={desabilitado ? "Você não pode alterar o próprio papel" : undefined}
        onChange={(e) => e.currentTarget.form?.requestSubmit()}
        style={{
          font: "inherit", fontSize: 12.5, padding: "3px 6px",
          border: "1px solid #e3e2dd", borderRadius: 6,
          background: desabilitado ? "#f2f1ee" : "#fff",
          color: desabilitado ? "#8a897f" : "#0b0b0b",
          cursor: desabilitado ? "not-allowed" : "pointer",
        }}
      >
        <option value="">—</option>
        <option value="operador">operador</option>
        <option value="admin">admin</option>
      </select>
    </form>
  );
}
