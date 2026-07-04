# -*- coding: utf-8 -*-
"""
============================================================
 DE→PARA METABASE — data real de gravação dos vídeos
============================================================
 1. Autentica no Metabase reutilizando o app de Limpeza
    (cookies em metabase_cookies.json de lá; se vencidos,
    cole o cookie novo em cookies.txt na pasta da Limpeza)
 2. Baixa a question 19885 (Videos BO) inteira — ~540 mil
    linhas — e guarda um resumo local comprimido (cache 7 dias)
 3. Casa video_id_antigo do levantamento LDI com video_id do
    sistema antigo e acrescenta ao CSV/JSON:
      gravacao_data, gravacao_ano, mb_status, mb_titulo,
      mb_raiz, mb_arvore_path, mb_qtd_locais, depara_ok

 Uso:  py depara_metabase.py [--arquivo videos_PRF_....json]
                             [--refresh]  (força novo download)
============================================================
"""
import argparse
import csv
import glob
import gzip
import json
import os
import re
import sys
import time
from datetime import datetime

# Console do Windows às vezes não é UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PASTA_APP = os.path.dirname(os.path.abspath(sys.argv[0]))
PASTA_LIMPEZA = (r"C:\⚙️ Aplicativos\🦉 Relatório de Cursos - Árvores"
                 r" - Professores\6. Limpeza Unificada de Dados")
CARD_VIDEOS_BO = 19885
CACHE_DEPARA = os.path.join(PASTA_APP, "saida", "metabase_depara.json.gz")
DIAS_VALIDADE_CACHE = 7


def falha(msg):
    print(f"\n[ERRO] {msg}")
    return SystemExit(1)


def sessao_metabase():
    """Reutiliza a autenticação do app de Limpeza (mesmos cookies)."""
    if not os.path.isdir(PASTA_LIMPEZA):
        raise falha(f"Pasta do app de Limpeza não encontrada:\n       {PASTA_LIMPEZA}")
    sys.path.insert(0, PASTA_LIMPEZA)
    import experimento_metabase as mb
    s = mb.cria_sessao_autenticada()
    if not s:
        raise falha("Sem cookies do Metabase. Cole o cookie no cookies.txt da pasta da Limpeza\n"
                    "       (aba Network do DevTools, linha 'cookie:') e rode de novo.")
    if not mb.testar_conexao(s):
        raise falha("Cookies do Metabase vencidos ou Warp desligado.\n"
                    "       Ative o Warp e/ou cole um cookie novo no cookies.txt da Limpeza.")
    return s, mb


def baixar_depara(force=False):
    """Baixa a question inteira e resume num dict {video_id: {...}} (cache local).
    O cache é reusado sempre que existir e estiver dentro da validade — mesmo em
    formato antigo (sem 'dur'); nesse caso a prova por duração fica em branco até
    o próximo --refresh (que exige Warp ativo)."""
    if os.path.exists(CACHE_DEPARA) and not force:
        idade_h = (time.time() - os.path.getmtime(CACHE_DEPARA)) / 3600
        if idade_h <= DIAS_VALIDADE_CACHE * 24:
            print(f"[1/3] Reusando de→para local (baixado há {idade_h:.1f}h) — use --refresh p/ forçar")
            with gzip.open(CACHE_DEPARA, "rt", encoding="utf-8") as f:
                depara = json.load(f)
            if not any("dur" in v for v in depara.values()):
                print("      (cache antigo sem duração — a prova por duração virá no próximo --refresh com Warp)")
            return depara

    s, mb = sessao_metabase()
    print(f"[1/3] Baixando question {CARD_VIDEOS_BO} (Videos BO) inteira do Metabase...")
    r = s.post(f"{mb.METABASE_URL}/api/card/{CARD_VIDEOS_BO}/query/json",
               json={"parameters": []}, timeout=600)
    if r.status_code != 200:
        raise falha(f"Metabase respondeu HTTP {r.status_code}: {r.text[:300]}")
    linhas = r.json()
    print(f"      {len(linhas):,} linhas recebidas".replace(",", "."))

    depara = {}
    for l in linhas:
        vid = str(l.get("video_id") or "")
        if not vid:
            continue
        p = l.get("arvore_title_path") or ""
        if vid in depara:
            depara[vid]["n"] += 1
            # guarda TODOS os caminhos do vídeo na árvore (p/ varredura por tópico
            # na sugestão automática do Visualizador); limite defensivo de 12
            ps = depara[vid]["paths"]
            if p and p not in ps and len(ps) < 12:
                ps.append(p)
            continue
        depara[vid] = {
            "data": l.get("video_data_criacao") or "",
            "status": l.get("video_status") or "",
            "titulo": (l.get("video_titulo") or "").strip(),
            "raiz": l.get("raiz") or "",
            "path": p,
            "paths": [p] if p else [],
            "dur": (l.get("video_duracao") or "").strip(),
            "n": 1,
        }
    os.makedirs(os.path.dirname(CACHE_DEPARA), exist_ok=True)
    with gzip.open(CACHE_DEPARA, "wt", encoding="utf-8") as f:
        json.dump(depara, f, ensure_ascii=False)
    print(f"      {len(depara):,} vídeos únicos no de→para (cache salvo)".replace(",", "."))
    return depara


def escolher_arquivo(nome):
    pasta = os.path.join(PASTA_APP, "saida")
    if nome:
        caminho = os.path.join(pasta, os.path.basename(nome))
        if not os.path.exists(caminho):
            raise falha(f"Arquivo não encontrado: {caminho}")
        return caminho
    arqs = [a for a in glob.glob(os.path.join(pasta, "videos_*.json"))
            if "metabase" not in os.path.basename(a)]
    if not arqs:
        raise falha("Nenhum levantamento videos_*.json na pasta saida.")
    return max(arqs, key=os.path.getmtime)


def _segundos(dur):
    """Aceita 'HH:MM:SS(.ff)', 'MM:SS' ou número puro; devolve segundos ou None."""
    s = str(dur or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$", s)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.match(r"^(\d+):(\d+(?:\.\d+)?)$", s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.match(r"^\d+(?:\.\d+)?$", s)
    return float(s) if m else None


def _confere_duracao(dur_ldi, dur_mb):
    """Confere se as durações batem, com tolerância adaptativa.
    O sistema antigo às vezes guarda a duração arredondada ao minuto cheio
    (termina em ':00'); nesse caso comparamos por minuto (tolerância 60s).
    Quando o antigo tem segundos, a comparação é apertada (5s).
    Retorna 'sim' (bate), 'nao' (diverge de verdade) ou '' (falta dado)."""
    a, b = _segundos(dur_ldi), _segundos(dur_mb)
    if a is None or b is None:
        return ""
    arredondado = str(dur_mb).strip().endswith(":00")
    tol = 60 if arredondado else 5
    return "sim" if abs(a - b) <= tol else "nao"


def mesclar(depara, caminho):
    print(f"[2/3] Casando com {os.path.basename(caminho)}...")
    dados = json.load(open(caminho, encoding="utf-8"))

    NOVAS = ["gravacao_data", "gravacao_ano", "mb_status", "mb_titulo",
             "mb_raiz", "mb_arvore_path", "mb_duracao", "mb_qtd_locais",
             "depara_ok", "depara_confere"]
    casados = com_id = videos = 0
    confere = {"sim": 0, "nao": 0, "": 0}
    por_ano = {}
    saida = []
    for l in dados:
        eh_video = bool(l.get("bloco_id"))
        vid = str(l.get("video_id_antigo") or "").strip()
        m = depara.get(vid) if vid else None
        if eh_video:
            videos += 1
            if vid:
                com_id += 1
            if m:
                casados += 1
                ano = (m["data"] or "")[:4] or "s/ data"
                por_ano[ano] = por_ano.get(ano, 0) + 1
        novo = {}
        for k, v in l.items():
            if k in NOVAS:
                continue  # re-execução: substitui as colunas do de→para
            novo[k] = v
            if k == "video_id_antigo":
                novo["gravacao_data"] = m["data"] if m else ""
                novo["gravacao_ano"] = (m["data"] or "")[:4] if m else ""
                novo["mb_status"] = m["status"] if m else ""
                novo["mb_titulo"] = m["titulo"] if m else ""
                novo["mb_raiz"] = m["raiz"] if m else ""
                novo["mb_arvore_path"] = m["path"] if m else ""
                novo["mb_duracao"] = m.get("dur", "") if m else ""
                novo["mb_qtd_locais"] = m["n"] if m else ""
                novo["depara_ok"] = ("sim" if m else ("nao" if (eh_video and vid) else ""))
                cf = _confere_duracao(l.get("video_duracao"), m.get("dur")) if m else ""
                novo["depara_confere"] = cf
                if m and eh_video:
                    confere[cf] += 1
        for k in NOVAS:  # segurança se video_id_antigo não existia na linha
            novo.setdefault(k, "")
        saida.append(novo)

    json.dump(saida, open(caminho, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    base = caminho[:-5]
    colunas = list(saida[0].keys())
    try:
        f = open(base + ".csv", "w", newline="", encoding="utf-8-sig")
    except PermissionError:  # CSV aberto no Excel
        base = base + time.strftime("_%Hh%M")
        f = open(base + ".csv", "w", newline="", encoding="utf-8-sig")
        print(f"      (CSV estava aberto no Excel — salvei como {os.path.basename(base)}.csv)")
    with f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(saida)

    print(f"[3/3] Concluído!")
    print(f"      vídeos no levantamento : {videos}")
    print(f"      com ID antigo          : {com_id}")
    pct = casados / com_id * 100 if com_id else 0
    print(f"      casados no Metabase    : {casados} ({pct:.1f}% dos com ID)")
    print(f"      sem casar              : {com_id - casados}")
    print(f"      prova por duração      : {confere['sim']} batem · "
          f"{confere['nao']} DIVERGEM ⚠ · {confere['']} sem dado p/ comparar")
    print(f"      por ano de gravação real:")
    for ano in sorted(por_ano):
        print(f"        {ano}: {por_ano[ano]}")
    print(f"      arquivos atualizados: {os.path.basename(caminho)} + CSV")


def main():
    p = argparse.ArgumentParser(description="De→para Metabase (data real de gravação)")
    p.add_argument("--arquivo", help="videos_*.json específico (padrão: o mais recente)")
    p.add_argument("--refresh", action="store_true", help="força novo download do Metabase")
    p.add_argument("--agendado", action="store_true", help="não pede ENTER no final")
    args = p.parse_args()

    print("=" * 60)
    print(f" DE→PARA METABASE  |  {datetime.now():%d/%m/%Y %H:%M}")
    print("=" * 60)
    depara = baixar_depara(force=args.refresh)
    mesclar(depara, escolher_arquivo(args.arquivo))
    if not args.agendado:
        input("\nPressione ENTER para fechar...")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code and "--agendado" not in sys.argv:
            input("\nPressione ENTER para fechar...")
        raise
