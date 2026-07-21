"use client";

import { useState, type CSSProperties } from "react";
import { disparar } from "./actions";

const estiloCampo: CSSProperties = {
  width: "100%", font: "inherit", padding: "8px 11px",
  border: "1px solid #e3e2dd", borderRadius: 8, boxSizing: "border-box",
};

export function FormDisparo() {
  const [modo, setModo] = useState<"termo" | "ids">("termo");

  return (
    <form
      action={disparar}
      style={{
        display: "flex", flexDirection: "column", gap: 10,
        padding: 16, marginBottom: 24,
        border: "1px solid #e3e2dd", borderRadius: 10, background: "#fff",
      }}
    >
      <div style={{ display: "flex", gap: 18, fontSize: 13 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input
            type="radio" name="modo" value="termo"
            checked={modo === "termo"} onChange={() => setModo("termo")}
          />
          Por termo de busca
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
          <input
            type="radio" name="modo" value="ids"
            checked={modo === "ids"} onChange={() => setModo("ids")}
          />
          Por IDs colados do admin
        </label>
      </div>

      {modo === "termo" ? (
        <input
          type="text" name="termo" required placeholder="Ex.: PRF"
          style={estiloCampo}
        />
      ) : (
        <>
          <textarea
            name="ids" required rows={4}
            placeholder="Cole URLs ou UUIDs do admin, um por linha (ou separados por vírgula/espaço)"
            style={{ ...estiloCampo, resize: "vertical", font: "inherit" }}
          />
          <input
            type="text" name="rotulo" required placeholder="Rótulo do lote (obrigatório) — ex.: Reforço PRF turma 2"
            style={estiloCampo}
          />
        </>
      )}

      <button
        type="submit"
        style={{
          alignSelf: "flex-start", font: "inherit", fontWeight: 600, cursor: "pointer",
          background: "#2a78d6", color: "#fff", border: 0, borderRadius: 8,
          padding: "8px 16px",
        }}
      >
        Disparar coleta
      </button>
    </form>
  );
}
