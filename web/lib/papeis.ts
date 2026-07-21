import { notFound, redirect } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { criarClienteServidor } from "./supabase/servidor";

// Gate de papel reutilizável — lib server-only (não é "use server": exporta
// helpers, não actions). Toda tela/action re-checa o papel NO SERVIDOR.
export async function exigirPapel(
  papeis: string[],
  aoFalhar: "redirect" | "notFound"
): Promise<User> {
  const supabase = await criarClienteServidor();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || !papeis.includes(String(user.app_metadata?.role ?? ""))) {
    if (aoFalhar === "notFound") notFound();
    redirect("/login");
  }
  return user;
}

export async function exigirAdmin(
  aoFalhar: "redirect" | "notFound" = "redirect"
): Promise<User> {
  return exigirPapel(["admin"], aoFalhar);
}

export async function exigirOperador(
  aoFalhar: "redirect" | "notFound" = "redirect"
): Promise<User> {
  return exigirPapel(["admin", "operador"], aoFalhar);
}
