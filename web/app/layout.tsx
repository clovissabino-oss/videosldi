import type { ReactNode } from "react";

export const metadata = {
  title: "Painel de Conteúdo",
  description: "Auditoria de conteúdo dos cursos LDI — leitura para o time",
};

export default function LayoutRaiz({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}
