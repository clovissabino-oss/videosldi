"use server";

import { redirect } from "next/navigation";
import { criarClienteAdmin } from "../../lib/supabase/admin";
import { exigirAdmin } from "../../lib/papeis";

const DOMINIO_APROVADO = "@estrategia.com";
const PAPEIS_VALIDOS = ["", "operador", "admin"];

export async function convidarUsuario(formData: FormData) {
  await exigirAdmin();
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) redirect("/admin?msg=email");
  if (email.endsWith(DOMINIO_APROVADO)) redirect("/admin?msg=dominio");

  const admin = criarClienteAdmin();
  const { error } = await admin.auth.admin.inviteUserByEmail(email);
  if (error) {
    console.error("[admin] convidar:", error.message);
    redirect("/admin?msg=erro");
  }
  redirect(`/admin?msg=convidado&email=${encodeURIComponent(email)}`);
}

export async function removerUsuario(formData: FormData) {
  const eu = await exigirAdmin();
  const id = String(formData.get("id") ?? "");
  const email = String(formData.get("email") ?? "");
  if (!id) redirect("/admin?msg=erro");
  if (id === eu.id) redirect("/admin?msg=proprio");

  const admin = criarClienteAdmin();
  const { error } = await admin.auth.admin.deleteUser(id);
  if (error) {
    console.error("[admin] remover:", error.message);
    redirect("/admin?msg=erro");
  }
  redirect(`/admin?msg=removido&email=${encodeURIComponent(email)}`);
}

export async function definirPapel(formData: FormData) {
  const eu = await exigirAdmin();
  const id = String(formData.get("id") ?? "");
  const email = String(formData.get("email") ?? "");
  const papel = String(formData.get("papel") ?? "");
  if (!id || !PAPEIS_VALIDOS.includes(papel)) redirect("/admin?msg=erro");
  if (id === eu.id) redirect("/admin?msg=proprio-papel");

  const admin = criarClienteAdmin();
  const { error } = await admin.auth.admin.updateUserById(id, {
    app_metadata: { role: papel || null },
  });
  if (error) {
    console.error("[admin] definirPapel:", error.message);
    redirect("/admin?msg=erro");
  }
  redirect(`/admin?msg=papel-definido&email=${encodeURIComponent(email)}`);
}
