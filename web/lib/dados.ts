import type { SupabaseClient } from "@supabase/supabase-js";

// A view snapshot_atual tem 1 linha por termo (só pronto=true).
// v1 = um termo por vez: pega o sincronizado mais recentemente.
export async function snapshotAtual(supabase: SupabaseClient) {
  const { data, error } = await supabase
    .from("snapshot_atual")
    .select("id, termo, resumo, sincronizado_em")
    .order("sincronizado_em", { ascending: false })
    .limit(1);
  if (error) throw new Error(`snapshot_atual: ${error.message}`);
  return data?.[0] ?? null;
}
