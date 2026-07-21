# -*- coding: utf-8 -*-
"""
============================================================
 VISUALIZADOR LDI — tela analítica dos vídeos por curso
============================================================
 Servidor local (Flask) que:
   - mostra a última extração em árvore Cursos > Capítulos >
     Aulas > Vídeos, com filtros e painel analítico
   - gerencia o cookie (status com validade + colar novo)
   - dispara nova extração direto da tela

 Uso:  py visualizador.py           (abre o navegador sozinho)
       py visualizador.py --sem-navegador
============================================================
"""
import glob
import gzip
import json
import os
import re
import sys
import threading
import time
import unicodedata
import webbrowser
from datetime import date, datetime
from difflib import SequenceMatcher

from flask import Flask, jsonify, request, send_file

# reusa as funções do extrator (mesma pasta)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extrator_ldi as ex
import config_util
import cookie_status

# PASTA_APP = onde ficam cookie.txt/config.json/saida (ao lado do .py ou do .exe)
PASTA_APP = os.path.dirname(os.path.abspath(sys.argv[0]))
# PASTA_RECURSOS = onde fica ui.html (dentro do bundle quando empacotado)
PASTA_RECURSOS = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
PORTA = 8765

app = Flask(__name__)

# ----------------------------------------------------------
# Cookie: status e troca
# ----------------------------------------------------------

def _decodifica_sid(cookie_bruto):
    """Extrai validade/e-mail do token __Secure-SID (o único que a API exige)."""
    return cookie_status.decodifica_sid(cookie_bruto)


def _status_cookie(probar=True):
    caminho = os.path.join(PASTA_APP, "cookie.txt")
    info = {
        "existe": os.path.exists(caminho),
        "valido": False,
        "http": None,
        "email": "",
        "expira_em": "",
        "dias_restantes": None,
        "atualizado_em": "",
        "termo": "",
    }
    try:
        info["termo"] = ex.carregar_config().get("termo_busca", "")
    except SystemExit:
        pass
    if not info["existe"]:
        return info
    info["atualizado_em"] = datetime.fromtimestamp(
        os.path.getmtime(caminho)).strftime("%d/%m/%Y %H:%M")
    try:
        cookie = ex.carregar_cookie()
    except SystemExit:
        return info
    sid = _decodifica_sid(cookie)
    if sid.get("expira_ts"):
        info["email"] = sid.get("email", "")
        info["expira_em"] = datetime.fromtimestamp(sid["expira_ts"]).strftime("%d/%m/%Y %H:%M")
        info["dias_restantes"] = round((sid["expira_ts"] - time.time()) / 86400, 1)
    if probar:
        try:
            cfg = ex.carregar_config()
            s = ex.montar_sessao(cfg, cookie)
            r = s.get(f"{ex.API}/bo/ldi/courses?page=1&per_page=1&sort=desc&order_by=created_at",
                      timeout=30)
            info["http"] = r.status_code
            info["valido"] = r.status_code == 200
        except Exception:
            info["http"] = 0
    return info


@app.get("/api/cookie/status")
def api_cookie_status():
    return jsonify(_status_cookie(probar=request.args.get("probar", "1") == "1"))


@app.post("/api/cookie")
def api_cookie_salvar():
    corpo = request.get_json(silent=True) or {}
    novo = (corpo.get("cookie") or "").strip()
    novo = re.sub(r"^cookie\s*:\s*", "", novo, flags=re.I)
    novo = " ".join(novo.split())
    if len(novo) < 50 or "=" not in novo:
        return jsonify({"erro": "Isso não parece um cookie — copie o valor inteiro da linha 'cookie:' do DevTools."}), 400
    with open(os.path.join(PASTA_APP, "cookie.txt"), "w", encoding="utf-8") as f:
        f.write(novo + "\n")
    termo = (corpo.get("termo") or "").strip()
    if termo:
        config_util.atualizar_termo(os.path.join(PASTA_APP, "config.json"), termo)
    return jsonify(_status_cookie(probar=True))


# ----------------------------------------------------------
# Extrações disponíveis e dados
# ----------------------------------------------------------

def _pasta_saida():
    cfg = ex.carregar_config()
    pasta = os.path.join(PASTA_APP, cfg["pasta_saida"])
    os.makedirs(pasta, exist_ok=True)
    return pasta


@app.get("/api/extracoes")
def api_extracoes():
    itens = []
    for caminho in glob.glob(os.path.join(_pasta_saida(), "videos_*.json")):
        nome = os.path.basename(caminho)
        m = re.match(r"videos_(.+)_(\d{4}-\d{2}-\d{2})\.json$", nome)
        itens.append({
            "arquivo": nome,
            "termo": m.group(1).replace("_", " ") if m else nome,
            "data": m.group(2) if m else "",
            "tamanho_kb": round(os.path.getsize(caminho) / 1024),
        })
    itens.sort(key=lambda i: (i["data"], i["arquivo"]), reverse=True)
    return jsonify(itens)


@app.get("/api/dados")
def api_dados():
    nome = os.path.basename(request.args.get("arquivo", ""))  # sem path traversal
    caminho = os.path.join(_pasta_saida(), nome)
    if not (nome.endswith(".json") and os.path.exists(caminho)):
        return jsonify({"erro": "arquivo não encontrado"}), 404
    return send_file(caminho, mimetype="application/json")


# ----------------------------------------------------------
# Análises salvas (contexto: extração + filtros + cursos removidos)
# ----------------------------------------------------------
ARQ_ANALISES = os.path.join(PASTA_APP, "analises.json")
_trava_analises = threading.Lock()


def _ler_analises():
    if not os.path.exists(ARQ_ANALISES):
        return []
    try:
        with open(ARQ_ANALISES, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _gravar_analises(analises):
    with open(ARQ_ANALISES, "w", encoding="utf-8") as f:
        json.dump(analises, f, ensure_ascii=False, indent=1)


@app.get("/api/analises")
def api_analises():
    return jsonify(_ler_analises())


@app.post("/api/analises")
def api_analises_salvar():
    corpo = request.get_json(silent=True) or {}
    nome = (corpo.get("nome") or "").strip()
    if not nome:
        return jsonify({"erro": "Dê um nome para a análise."}), 400
    with _trava_analises:
        analises = [a for a in _ler_analises() if a.get("nome") != nome]
        analises.append({"nome": nome,
                         "salva_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
                         "estado": corpo.get("estado") or {}})
        analises.sort(key=lambda a: str(a.get("nome", "")).lower())
        _gravar_analises(analises)
    return jsonify({"ok": True})


@app.post("/api/analises/excluir")
def api_analises_excluir():
    corpo = request.get_json(silent=True) or {}
    nome = (corpo.get("nome") or "").strip()
    with _trava_analises:
        _gravar_analises([a for a in _ler_analises() if a.get("nome") != nome])
    return jsonify({"ok": True})


# ----------------------------------------------------------
# Propostas de substituição de vídeos (por capítulo/aula/vídeo)
# ----------------------------------------------------------
ARQ_PROPOSTAS = os.path.join(PASTA_APP, "propostas.json")
_trava_propostas = threading.Lock()


def _ler_propostas():
    if not os.path.exists(ARQ_PROPOSTAS):
        return []
    try:
        with open(ARQ_PROPOSTAS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _gravar_propostas(propostas):
    with open(ARQ_PROPOSTAS, "w", encoding="utf-8") as f:
        json.dump(propostas, f, ensure_ascii=False, indent=1)


@app.get("/api/propostas")
def api_propostas():
    return jsonify(_ler_propostas())


@app.post("/api/propostas")
def api_propostas_salvar():
    import uuid
    corpo = request.get_json(silent=True) or {}
    if not (corpo.get("propostos") or corpo.get("observacao")):
        return jsonify({"erro": "Inclua ao menos um vídeo proposto ou uma observação."}), 400
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    with _trava_propostas:
        propostas = _ler_propostas()
        pid = corpo.get("id") or ""
        existente = next((p for p in propostas if p.get("id") == pid), None)
        if existente:
            corpo["criada_em"] = existente.get("criada_em", agora)
            propostas = [p for p in propostas if p.get("id") != pid]
        else:
            corpo["id"] = pid or uuid.uuid4().hex[:12]
            corpo["criada_em"] = agora
        corpo["atualizada_em"] = agora
        propostas.append(corpo)
        _gravar_propostas(propostas)
    return jsonify({"ok": True, "id": corpo["id"]})


@app.post("/api/propostas/excluir")
def api_propostas_excluir():
    corpo = request.get_json(silent=True) or {}
    pid = (corpo.get("id") or "").strip()
    with _trava_propostas:
        _gravar_propostas([p for p in _ler_propostas() if p.get("id") != pid])
    return jsonify({"ok": True})


# ----------------------------------------------------------
# Estoque do professor — fonte preferencial: árvores .xlsx da
# pasta da Limpeza (frescas, TODOS os caminhos por vídeo);
# complemento: question 19885 (gz) p/ professores sem árvore.
# Sugestão automática de substituição por similaridade.
# ----------------------------------------------------------
CACHE_DEPARA = os.path.join(PASTA_APP, "saida", "metabase_depara.json.gz")
PASTA_ARVORES = (r"C:\⚙️ Aplicativos\🦉 Relatório de Cursos - Árvores"
                 r" - Professores\6. Limpeza Unificada de Dados\downloads_metabase")
CACHE_ARVORES = os.path.join(PASTA_APP, "saida", "estoque_arvores.json.gz")
_estoque = {"dados": None, "indice": None, "versao": None, "base_q": {}}
_trava_estoque = threading.Lock()


def _arquivos_arvore():
    """Último arvore_*.xlsx de cada professor (só a raiz da pasta; ignora arquivados)."""
    itens = {}
    try:
        nomes = os.listdir(PASTA_ARVORES)
    except OSError:
        return {}
    for n in nomes:
        m = re.match(r"arvore_(.+)_(\d{8}_\d{6})\.xlsx$", n, re.I)
        if not m:
            continue
        chave, ts = m.group(1).lower(), m.group(2)
        if chave not in itens or ts > itens[chave][1]:
            itens[chave] = (os.path.join(PASTA_ARVORES, n), ts)
    return {k: v[0] for k, v in itens.items()}


def _ler_arvore_xlsx(caminho):
    """Lê um arvore_*.xlsx → lista de registros {id, titulo, raiz, path, ...}."""
    import warnings
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        linhas = ws.iter_rows(values_only=True)
        try:
            cab = [str(c or "").strip().lower() for c in next(linhas)]
        except StopIteration:
            return []
        ix = {nome: cab.index(nome) for nome in
              ("raiz", "video_id", "video_titulo", "video_status",
               "video_data_criacao", "video_duracao", "arvore_title_path")
              if nome in cab}
        nos = [cab.index(f"no{i}") for i in range(1, 8) if f"no{i}" in cab]
        regs = []
        for row in linhas:
            def col(nome):
                i = ix.get(nome)
                v = row[i] if i is not None and i < len(row) else None
                return "" if v is None else str(v).strip()
            vid = col("video_id").split(".")[0]     # openpyxl lê '261680.0'
            if not vid.isdigit():
                continue
            segs = [str(row[i]).strip() for i in nos
                    if i < len(row) and row[i] is not None and str(row[i]).strip()]
            status = col("video_status")
            if status.lower() == "disponivel":      # xlsx vem sem acento
                status = "Disponível"
            regs.append({
                "id": vid,
                "titulo": col("video_titulo"),
                "raiz": col("raiz"),
                "data": col("video_data_criacao"),
                "dur": col("video_duracao"),
                "status": status,
                "path": " >-> ".join(segs) if segs else col("arvore_title_path"),
            })
        return regs
    finally:
        wb.close()


def _carregar_arvores():
    """Consolida as árvores .xlsx em {video_id: {...}} com cache local em gz."""
    arquivos = _arquivos_arvore()
    if not arquivos:
        return {}, {}
    manifesto = {os.path.basename(c): os.path.getmtime(c) for c in arquivos.values()}
    if os.path.exists(CACHE_ARVORES):
        try:
            with gzip.open(CACHE_ARVORES, "rt", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("manifesto") == manifesto:
                return cache["dados"], manifesto
        except Exception:
            pass
    dados = {}
    for caminho in sorted(arquivos.values(), key=os.path.getmtime):
        for r in _ler_arvore_xlsx(caminho):
            d = dados.get(r["id"])
            if d is None:
                dados[r["id"]] = d = {"titulo": r["titulo"], "data": r["data"],
                                      "status": r["status"], "raiz": r["raiz"],
                                      "dur": r["dur"], "paths": [], "n": 0}
            d["n"] += 1
            if r["path"] and r["path"] not in d["paths"] and len(d["paths"]) < 12:
                d["paths"].append(r["path"])
    try:
        os.makedirs(os.path.dirname(CACHE_ARVORES), exist_ok=True)
        with gzip.open(CACHE_ARVORES, "wt", encoding="utf-8") as f:
            json.dump({"manifesto": manifesto, "dados": dados}, f, ensure_ascii=False)
    except Exception:
        pass
    return dados, manifesto


def _carregar_estoque():
    """Estoque unificado em memória; recarrega quando qualquer fonte mudar."""
    gz_mtime = os.path.getmtime(CACHE_DEPARA) if os.path.exists(CACHE_DEPARA) else None
    arquivos = _arquivos_arvore()
    versao = (gz_mtime, tuple(sorted(
        (os.path.basename(c), os.path.getmtime(c)) for c in arquivos.values())))
    if gz_mtime is None and not arquivos:
        return None
    with _trava_estoque:
        if _estoque["dados"] is not None and _estoque["versao"] == versao:
            return _estoque["dados"]
        base_q = {}
        if gz_mtime:
            with gzip.open(CACHE_DEPARA, "rt", encoding="utf-8") as f:
                base_q = json.load(f)
        arvores, _ = _carregar_arvores()
        # raízes cobertas pelas árvores frescas saem da base da question
        raizes_frescas = {_norm(v.get("raiz")) for v in arvores.values()}
        dados = {}
        for vid, v in base_q.items():
            if _norm(v.get("raiz")) not in raizes_frescas:
                v2 = dict(v)
                v2["fonte"] = "question"
                dados[vid] = v2
        for vid, v in arvores.items():
            v2 = dict(v)
            v2["fonte"] = "arvore"
            dados[vid] = v2
        idx = {}
        for vid, v in dados.items():
            raiz = (v.get("raiz") or "").strip() or "(sem raiz)"
            idx.setdefault(raiz, []).append(vid)
        _estoque.update(dados=dados, indice=idx, versao=versao, base_q=base_q,
                        n_arvores=len(arvores),
                        profs_frescos=sorted({(v.get("raiz") or "").strip()
                                              for v in arvores.values()}))
    return _estoque["dados"]


def _norm(s):
    """Normaliza nomes p/ comparação: minúsculo, sem acento, sem IDs/numeração."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"videosintra\s*[\d.,]+", " ", s)     # id "videosintra83.480" no nome
    s = re.sub(r"[-–—]\s*[\d.,]{4,9}\s*$", " ", s)   # "- 83480" no fim
    s = re.sub(r"^\s*[\d.,]+\s*[-–—.)]?\s*", " ", s) # numeração "2.1 -" no início
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _sim(a, b):
    """Similaridade 0..1 entre dois nomes (sequência + conjunto de palavras)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return round(max(seq, jac), 3)


def _paths_de(v):
    """Lista de caminhos do vídeo no estoque (cache novo tem 'paths'; antigo só 'path')."""
    ps = v.get("paths")
    if ps:
        return ps
    return [v["path"]] if v.get("path") else []


def _score_path(path, alvo):
    """Semelhança do tópico com o nome do alvo (melhor segmento do caminho)."""
    segs = [s.strip() for s in str(path or "").split(">->") if s.strip()]
    return max((_sim(s, alvo) for s in segs), default=0.0)


def _chave_natural(s):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", str(s or ""))]


@app.get("/api/estoque/status")
def api_estoque_status():
    dados = _carregar_estoque()
    if dados is None:
        return jsonify({"existe": False})
    datas = [os.path.getmtime(c) for c in _arquivos_arvore().values()]
    if os.path.exists(CACHE_DEPARA):
        datas.append(os.path.getmtime(CACHE_DEPARA))
    return jsonify({
        "existe": True,
        "n_videos": len(dados),
        "n_arvores": _estoque.get("n_arvores", 0),
        "n_profs_frescos": len(_estoque.get("profs_frescos", [])),
        "atualizado_em": datetime.fromtimestamp(max(datas)).strftime("%d/%m/%Y %H:%M")
                         if datas else "",
        "tem_paths_completos": _estoque.get("n_arvores", 0) > 0,
    })


@app.get("/api/estoque/raizes")
def api_estoque_raizes():
    if _carregar_estoque() is None:
        return jsonify({"erro": "Nenhuma fonte de estoque encontrada — exporte as árvores "
                                "na Limpeza ou rode o _depara_metabase.bat."}), 404
    q = _norm(request.args.get("q", ""))
    frescos = set(_estoque.get("profs_frescos", []))
    itens = [{"raiz": r, "n": len(v), "fresca": r in frescos}
             for r, v in _estoque["indice"].items() if not q or q in _norm(r)]
    itens.sort(key=lambda x: (not x["fresca"], -x["n"], x["raiz"].lower()))
    return jsonify(itens[:40])


@app.get("/api/estoque/topicos")
def api_estoque_topicos():
    dados = _carregar_estoque()
    if dados is None:
        return jsonify({"erro": "Cache do de→para não encontrado — rode o _depara_metabase.bat antes."}), 404
    raiz = request.args.get("raiz", "")
    alvo = request.args.get("q", "")
    grupos = {}
    for vid in _estoque["indice"].get(raiz, []):
        for p in _paths_de(dados[vid]):
            grupos[p] = grupos.get(p, 0) + 1
    itens = [{"path": p, "n": n, "score": _score_path(p, alvo) if alvo else 0.0}
             for p, n in grupos.items()]
    itens.sort(key=lambda x: (-x["score"], -x["n"], _chave_natural(x["path"])))
    return jsonify(itens[:300])


@app.post("/api/estoque/sugerir")
def api_estoque_sugerir():
    dados = _carregar_estoque()
    if dados is None:
        return jsonify({"erro": "Cache do de→para não encontrado — rode o _depara_metabase.bat antes."}), 404
    corpo = request.get_json(silent=True) or {}
    raiz = corpo.get("raiz") or ""
    sel = set(corpo.get("paths") or [])
    atuais = corpo.get("atuais") or []   # [{nome, id}]
    itens = []
    for vid in _estoque["indice"].get(raiz, []):
        v = dados[vid]
        vpaths = _paths_de(v)
        if sel and not any(p in sel for p in vpaths):
            continue
        melhor, melhor_sim = None, 0.0
        for a in atuais:
            s = _sim(v.get("titulo"), a.get("nome"))
            if s > melhor_sim:
                melhor_sim, melhor = s, a
        path_sel = next((p for p in vpaths if p in sel), vpaths[0] if vpaths else "")
        itens.append({
            "id": vid,
            "titulo": v.get("titulo") or "",
            "data": v.get("data") or "",
            "ano": (v.get("data") or "")[:4],
            "dur": v.get("dur") or "",
            "status": v.get("status") or "",
            "path": path_sel,
            "n_locais": v.get("n", 1),
            "match_nome": (melhor or {}).get("nome", ""),
            "match_id": (melhor or {}).get("id", ""),
            "sim": melhor_sim,
        })
    itens.sort(key=lambda x: (_chave_natural(x["path"]), _chave_natural(x["titulo"])))
    return jsonify({"itens": itens, "total": len(itens)})


@app.post("/api/estoque/resolver")
def api_estoque_resolver():
    """Resolve IDs digitados → nome/ano/duração do vídeo no estoque."""
    dados = _carregar_estoque()
    if dados is None:
        return jsonify({"erro": "Cache do de→para não encontrado — rode o _depara_metabase.bat antes."}), 404
    corpo = request.get_json(silent=True) or {}
    ids = [str(i).strip() for i in (corpo.get("ids") or []) if str(i).strip()]
    encontrados, faltando = {}, []
    for i in ids[:200]:
        v = dados.get(i)
        fora = False
        if not v:  # não está nas árvores vigentes — tenta a base ampla (question)
            v = _estoque.get("base_q", {}).get(i)
            fora = v is not None
        if v:
            encontrados[i] = {
                "titulo": v.get("titulo") or "",
                "ano": (v.get("data") or "")[:4],
                "data": v.get("data") or "",
                "dur": v.get("dur") or "",
                "status": v.get("status") or "",
                "raiz": v.get("raiz") or "",
                "fora_da_arvore": fora,
            }
        else:
            faltando.append(i)
    return jsonify({"encontrados": encontrados, "faltando": faltando})


# ----------------------------------------------------------
# Nova extração (em thread, com progresso)
# ----------------------------------------------------------
ESTADO = {"rodando": False, "etapa": "", "feitos": 0, "total": 0,
          "erro": "", "arquivo": "", "termo": ""}


def _extrair(termo):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    try:
        cfg = ex.carregar_config()
        cfg["termo_busca"] = termo
        sessao = ex.montar_sessao(cfg, ex.carregar_cookie())

        ESTADO.update(etapa="Buscando cursos...", feitos=0, total=0)
        cursos = ex.listar_cursos(sessao, termo)
        if cfg["filtro_local"]:
            rx = re.compile(cfg["filtro_local"], re.I)
            cursos = [c for c in cursos if rx.search(c.get("name") or "")]
        if not cursos:
            raise RuntimeError(f'Nenhum curso encontrado para "{termo}".')

        tarefas = []
        for curso in cursos:
            for cap in (curso.get("content_tree_cache") or []):
                for item in (cap.get("items") or []):
                    btc = {**(item.get("simple_block_type_count") or {}),
                           **(item.get("block_type_count") or {})}
                    if any(btc.get(t) for t in ex.TIPOS_VIDEO):
                        tarefas.append((curso, cap, item))
        ids_unicos = sorted({item["item_id"] for _, _, item in tarefas})
        ESTADO.update(etapa=f"Baixando blocos de {len(ids_unicos)} aulas ({len(cursos)} cursos)...",
                      total=len(ids_unicos))

        blocos_por_item, erros_por_item = {}, {}

        def baixar(item_id):
            j = ex.get_json(sessao, f"{ex.API}/bo/ldi/blocks?item_id={item_id}")
            return item_id, (j.get("data") or [])

        with ThreadPoolExecutor(max_workers=int(cfg["concorrencia"])) as pool:
            futs = {pool.submit(baixar, i): i for i in ids_unicos}
            for fut in as_completed(futs):
                item_id = futs[fut]
                try:
                    _, blocos = fut.result()
                    blocos_por_item[item_id] = blocos
                except BaseException as e:
                    erros_por_item[item_id] = str(e)
                ESTADO["feitos"] += 1

        ESTADO.update(etapa="Gravando arquivos...")
        linhas = []
        for curso, cap, item in tarefas:
            iid = item["item_id"]
            if iid in erros_por_item:
                linhas.append(ex.linha(cfg, curso, cap, item, None, "ERRO: " + erros_por_item[iid]))
                continue
            achou = False
            for b in blocos_por_item.get(iid, []):
                if b.get("type") in ex.TIPOS_VIDEO:
                    linhas.append(ex.linha(cfg, curso, cap, item, b))
                    achou = True
            if not achou:
                linhas.append(ex.linha(cfg, curso, cap, item, None,
                                       "aula sem bloco de video na versao atual"))

        def chave_path(p):
            return [int(x) if x.isdigit() else 0 for x in str(p or "").split(".")]
        linhas.sort(key=lambda l: (l["curso_nome"], l["capitulo_ordem"] or 0,
                                   chave_path(l["aula_path"]), l["bloco_ordem"] or 0))

        termo_arq = re.sub(r"[^\w\-]+", "_", termo)
        base = os.path.join(_pasta_saida(), f"videos_{termo_arq}_{date.today():%Y-%m-%d}")
        import csv as _csv
        colunas = list(linhas[0].keys())
        try:
            f = open(base + ".csv", "w", newline="", encoding="utf-8-sig")
        except PermissionError:  # CSV anterior aberto no Excel — usa sufixo
            base = base + time.strftime("_%Hh%M")
            f = open(base + ".csv", "w", newline="", encoding="utf-8-sig")
        with f:
            w = _csv.DictWriter(f, fieldnames=colunas, delimiter=";", quoting=_csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(linhas)
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(linhas, f, ensure_ascii=False, indent=1)

        ESTADO.update(etapa="Concluído!", arquivo=os.path.basename(base + ".json"))
    except BaseException as e:  # inclui SystemExit do extrator (ex.: cookie vencido)
        msg = str(e) or e.__class__.__name__
        if isinstance(e, SystemExit):
            msg = "Cookie vencido ou inválido — atualize pelo botão Cookie."
        ESTADO.update(erro=msg, etapa="Falhou")
    finally:
        ESTADO["rodando"] = False


@app.post("/api/extrair")
def api_extrair():
    if ESTADO["rodando"]:
        return jsonify({"erro": "Já existe uma extração em andamento."}), 409
    corpo = request.get_json(silent=True) or {}
    termo = (corpo.get("termo") or "").strip() or ex.carregar_config()["termo_busca"]
    ESTADO.update(rodando=True, etapa="Iniciando...", feitos=0, total=0,
                  erro="", arquivo="", termo=termo)
    threading.Thread(target=_extrair, args=(termo,), daemon=True).start()
    return jsonify({"ok": True, "termo": termo})


@app.get("/api/extrair/status")
def api_extrair_status():
    return jsonify(ESTADO)


# ----------------------------------------------------------
# Interface
# ----------------------------------------------------------
@app.get("/")
def raiz():
    return send_file(os.path.join(PASTA_RECURSOS, "ui.html"))


@app.get("/estoque")
def pagina_estoque():
    return send_file(os.path.join(PASTA_RECURSOS, "estoque.html"))


def main():
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORTA}")).start()
    print("=" * 56)
    print(f"  VISUALIZADOR LDI  |  http://127.0.0.1:{PORTA}")
    print("  (deixe esta janela aberta; Ctrl+C para encerrar)")
    print("=" * 56)
    app.run(host="127.0.0.1", port=PORTA, debug=False)


if __name__ == "__main__":
    main()
