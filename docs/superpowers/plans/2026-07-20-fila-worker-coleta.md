# Fila de coleta + worker no VPS (Fase 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Uma fila no Supabase e um worker Python (systemd no VPS) que a observa, roda `coletor_ldi.coletar()` + o sync, reporta status/progresso, honra cancelamento e avisa (e-mail Resend) quando o cookie do LDI cai.

**Architecture:** O worker faz polling da tabela `coleta_pedido` no Supabase (via REST, service_role — reusa `sync_supabase._config/_headers`), carrega o cookie de `config_ldi`, e chama a coleta existente passando um callback de progresso/cancelamento. Publica `cookie_status`. Tudo reusa o pipeline provado; as mudanças no código atual são mínimas (um kwarg no `coletar` e a extração da validade de cookie para um módulo compartilhado).

**Tech Stack:** Python 3.12, `requests` (sem dep nova), SQLite, Supabase (Postgres+PostgREST), Resend (REST), `unittest`, systemd. pt-BR.

## Global Constraints
- **Não regredir** coletor/sync/telas locais — só adicionar (worker + callback opcional).
- **Reusar** `sync_supabase._config/_headers` (REST/service_role) e `extrator_ldi` (sessão/cookie); DRY.
- **Testes `unittest`** (`py -m unittest discover -s tests`), não pytest.
- **Segredos nunca no git nem no navegador:** `config_ldi.cookie` só service_role; RESEND/SERVICE_KEY só no servidor.
- **Single-flight:** um pedido por vez (o coletor assume).
- Spec: `docs/superpowers/specs/2026-07-20-fila-worker-coleta-design.md`.

---

### Task 1: Schema da fila (`supabase/schema_coleta.sql`)

**Files:** Create `supabase/schema_coleta.sql`.

**Interfaces:** Produces as tabelas `coleta_pedido`, `config_ldi`, `cookie_status` que o worker (Task 4) e o app (Fase 4) consomem.

- [ ] **Step 1: Escrever o SQL** — `supabase/schema_coleta.sql`:
```sql
-- Fila de coleta + cookie do LDI + status do cookie (Fase 3).
-- Idempotente. Aplicar no SQL editor do Supabase ou via Management API.

create table if not exists coleta_pedido (
  id           bigserial primary key,
  tipo         text        not null check (tipo in ('termo','ids')),
  alvo         text        not null,
  rotulo       text,
  status       text        not null default 'pendente'
               check (status in ('pendente','rodando','cancelando',
                                  'cancelada','concluida','erro','aguardando_cookie')),
  progresso    text,
  mensagem     text,
  extracao_id  int,
  pedido_por   text,
  criado_em    timestamptz not null default now(),
  iniciado_em  timestamptz,
  concluido_em timestamptz
);
create index if not exists ix_coleta_pedido_fila
  on coleta_pedido (status, criado_em);

create table if not exists config_ldi (
  id             int primary key default 1 check (id = 1),
  cookie         text,
  atualizado_em  timestamptz not null default now(),
  atualizado_por text
);

create table if not exists cookie_status (
  id             int primary key default 1 check (id = 1),
  email          text,
  expira_em      timestamptz,
  dias_restantes numeric,
  valido         boolean not null default false,
  atualizado_em  timestamptz not null default now()
);

alter table coleta_pedido enable row level security;
alter table config_ldi    enable row level security;
alter table cookie_status enable row level security;

-- coleta_pedido: leitura autenticada; escrita só service_role (sem policy de escrita)
drop policy if exists "leitura autenticada" on coleta_pedido;
create policy "leitura autenticada" on coleta_pedido
  for select to authenticated using (true);

-- cookie_status: leitura autenticada (para o banner)
drop policy if exists "leitura autenticada" on cookie_status;
create policy "leitura autenticada" on cookie_status
  for select to authenticated using (true);

-- config_ldi: SEM policy nenhuma → authenticated não lê nem escreve; só service_role acessa.

grant select on coleta_pedido, cookie_status to authenticated;
```

- [ ] **Step 2: Aplicar e verificar** — no projeto Supabase (SQL editor ou Management API): rodar o arquivo; conferir as 3 tabelas e que `select * from config_ldi` como `anon`/`authenticated` é negado (RLS) e como `service_role` funciona.

- [ ] **Step 3: Commit** — `git add supabase/schema_coleta.sql && git commit -m "feat: schema da fila de coleta + cookie no Supabase (Fase 3)"`

---

### Task 2: Módulo `cookie_status.py` (validade do cookie, compartilhado)

**Files:** Create `cookie_status.py`; Modify `visualizador.py` (passa a importar); Test `tests/test_cookie_status.py`.

**Interfaces:**
- Produces: `decodifica_sid(cookie_bruto) -> dict` (`{email, expira_ts}` ou `{}`); `resumo_validade(cookie_bruto) -> dict` (`{email, expira_em, dias_restantes, valido}` — sem probe de rede; `valido` = tem exp no futuro).

- [ ] **Step 1: Teste que falha** — `tests/test_cookie_status.py`:
```python
import base64, json, time, unittest
import cookie_status

def _sid(email, exp):
    payload = base64.urlsafe_b64encode(
        json.dumps({"email": email, "exp": exp}).encode()).decode().rstrip("=")
    return f"__Secure-SID=x.{payload}.y; outra=coisa"

class TestCookieStatus(unittest.TestCase):
    def test_decodifica(self):
        d = cookie_status.decodifica_sid(_sid("a@b.com", 9999999999))
        self.assertEqual(d["email"], "a@b.com")
        self.assertEqual(d["expira_ts"], 9999999999)

    def test_sem_sid(self):
        self.assertEqual(cookie_status.decodifica_sid("nada aqui"), {})

    def test_resumo_valido_futuro(self):
        r = cookie_status.resumo_validade(_sid("a@b.com", int(time.time()) + 5 * 86400))
        self.assertTrue(r["valido"])
        self.assertEqual(r["email"], "a@b.com")
        self.assertGreater(r["dias_restantes"], 4)

    def test_resumo_vencido(self):
        r = cookie_status.resumo_validade(_sid("a@b.com", int(time.time()) - 10))
        self.assertFalse(r["valido"])

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest tests.test_cookie_status -v` → FAIL.

- [ ] **Step 3: Implementar** — `cookie_status.py`:
```python
# -*- coding: utf-8 -*-
"""Validade do cookie __Secure-SID do LDI (compartilhado: visualizador e worker)."""
import base64
import json
import re
import time
from datetime import datetime, timezone


def decodifica_sid(cookie_bruto):
    """Extrai {email, expira_ts} do token __Secure-SID; {} se não achar/decodificar."""
    m = re.search(r"__Secure-SID=([^;\s]+)", cookie_bruto or "")
    if not m:
        return {}
    try:
        payload = m.group(1).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        j = json.loads(base64.urlsafe_b64decode(payload))
        return {"email": j.get("email", ""), "expira_ts": j.get("exp")}
    except Exception:
        return {}


def resumo_validade(cookie_bruto):
    """Resumo sem rede: {email, expira_em(iso|None), dias_restantes(float|None), valido}.
    valido = há exp no futuro (não faz probe HTTP; o worker pode complementar com probe)."""
    sid = decodifica_sid(cookie_bruto)
    exp = sid.get("expira_ts")
    if not exp:
        return {"email": "", "expira_em": None, "dias_restantes": None, "valido": False}
    return {
        "email": sid.get("email", ""),
        "expira_em": datetime.fromtimestamp(exp, timezone.utc).isoformat(),
        "dias_restantes": round((exp - time.time()) / 86400, 1),
        "valido": exp > time.time(),
    }
```

- [ ] **Step 4: Refatorar `visualizador.py`** — trocar o corpo do `_decodifica_sid` local por delegação (evita duplicar a lógica). Em `visualizador.py`, adicionar no topo `import cookie_status` e substituir a função:
```python
def _decodifica_sid(cookie_bruto):
    """Extrai validade/e-mail do token __Secure-SID (o único que a API exige)."""
    return cookie_status.decodifica_sid(cookie_bruto)
```

- [ ] **Step 5: Rodar** — `py -m unittest tests.test_cookie_status -v` → PASS; e `py -m unittest discover -s tests` → tudo verde (visualizador não regrediu).

- [ ] **Step 6: Commit** — `git add cookie_status.py visualizador.py tests/test_cookie_status.py && git commit -m "feat: cookie_status compartilhado (extrai validade do visualizador)"`

---

### Task 3: Callback de progresso/cancelamento no coletor

**Files:** Modify `coletor_ldi.py`; Test `tests/test_coletor_progresso.py`.

**Interfaces:**
- Produces: `ColetaCancelada(Exception)`; `_baixar_lote(..., progresso=None)`; `coletar(..., progresso=None)`. `progresso` é `callable(feito:int, total:int)`; se levantar `ColetaCancelada`, o batch para e a exceção sobe (extração fica retomável).

- [ ] **Step 1: Teste que falha** — `tests/test_coletor_progresso.py`:
```python
import unittest
from unittest.mock import MagicMock, patch
import coletor_ldi

class TestProgressoCancel(unittest.TestCase):
    def _con(self):
        return MagicMock()

    @patch("coletor_ldi.banco_conteudo.gravar_blocos_da_aula")
    @patch("coletor_ldi.baixar_blocos", return_value=[])
    def test_callback_recebe_progresso(self, _bb, _gb):
        chamadas = []
        coletor_ldi._baixar_lote(MagicMock(), self._con(), 1, ["i1", "i2"], 2,
                                 progresso=lambda f, t: chamadas.append((f, t)))
        self.assertEqual(chamadas[-1], (2, 2))  # dispara ao terminar

    @patch("coletor_ldi.banco_conteudo.gravar_blocos_da_aula")
    @patch("coletor_ldi.baixar_blocos", return_value=[])
    def test_cancelamento_aborta(self, _bb, _gb):
        def cancela(f, t):
            raise coletor_ldi.ColetaCancelada()
        with self.assertRaises(coletor_ldi.ColetaCancelada):
            coletor_ldi._baixar_lote(MagicMock(), self._con(), 1, ["i1"], 1,
                                     progresso=cancela)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest tests.test_coletor_progresso -v` → FAIL.

- [ ] **Step 3: Implementar** — em `coletor_ldi.py`:

(a) Definir a exceção perto do topo (após os imports):
```python
class ColetaCancelada(Exception):
    """Sinalizado pelo callback de progresso para abortar a coleta em andamento."""
```

(b) `_baixar_lote` ganha `progresso=None` e chama o callback junto do print. DE a assinatura:
```python
def _baixar_lote(sessao, con, extracao_id, pendentes, concorrencia, videos_por_item=None):
```
PARA:
```python
def _baixar_lote(sessao, con, extracao_id, pendentes, concorrencia,
                 videos_por_item=None, progresso=None):
```
E o bloco final do loop. DE:
```python
            feitos += 1
            if feitos % 100 == 0 or feitos == len(pendentes):
                print(f"      ...{feitos}/{len(pendentes)}")
    return erros
```
PARA:
```python
            feitos += 1
            if feitos % 100 == 0 or feitos == len(pendentes):
                print(f"      ...{feitos}/{len(pendentes)}")
            if progresso and (feitos % 20 == 0 or feitos == len(pendentes)):
                progresso(feitos, len(pendentes))  # pode levantar ColetaCancelada
    return erros
```
(Nota: o `except Exception` de cada future é interno ao `try` do `fut.result()`; o `progresso(...)` fica FORA dele, então `ColetaCancelada` propaga sem ser engolida.)

(c) `coletar` ganha `progresso=None` e repassa às duas chamadas de `_baixar_lote`. DE a assinatura:
```python
def coletar(cfg, sessao, termo, caminho_banco, continuar=False, com_videos=False, ids=None):
```
PARA:
```python
def coletar(cfg, sessao, termo, caminho_banco, continuar=False, com_videos=False,
            ids=None, progresso=None):
```
E as duas chamadas de `_baixar_lote`. DE:
```python
        erros = _baixar_lote(sessao, con, extracao_id, pendentes,
                             cfg["concorrencia"], videos_por_item)
        if erros:  # 1 rodada de retry
            print(f"      retry de {len(erros)} aulas com falha...")
            erros = _baixar_lote(sessao, con, extracao_id, list(erros),
                                 cfg["concorrencia"], videos_por_item)
```
PARA:
```python
        erros = _baixar_lote(sessao, con, extracao_id, pendentes,
                             cfg["concorrencia"], videos_por_item, progresso)
        if erros:  # 1 rodada de retry
            print(f"      retry de {len(erros)} aulas com falha...")
            erros = _baixar_lote(sessao, con, extracao_id, list(erros),
                                 cfg["concorrencia"], videos_por_item, progresso)
```

- [ ] **Step 4: Rodar** — `py -m unittest tests.test_coletor_progresso -v` → PASS; suíte inteira verde.

- [ ] **Step 5: Commit** — `git add coletor_ldi.py tests/test_coletor_progresso.py && git commit -m "feat: coletar aceita callback de progresso/cancelamento (ColetaCancelada)"`

---

### Task 4: Worker `worker_coleta.py`

**Files:** Create `worker_coleta.py`; Test `tests/test_worker_coleta.py`.

**Interfaces:**
- Consumes: `sync_supabase._config/_headers`, `extrator_ldi` (montar_sessao/carregar_config/CookieVencido), `coletor_ldi` (coletar/extrair_ids/ColetaCancelada), `cookie_status.resumo_validade`.
- Produces: `pedido_para_coleta(row) -> (termo, ids)` (puro); `processar_pedido(row, ...)`; `main()` (laço). E-mail via `enviar_email_cookie(...)`.

- [ ] **Step 1: Teste que falha (parte pura)** — `tests/test_worker_coleta.py`:
```python
import unittest
import worker_coleta

class TestPedidoParaColeta(unittest.TestCase):
    def test_tipo_termo(self):
        termo, ids = worker_coleta.pedido_para_coleta(
            {"tipo": "termo", "alvo": "PRF", "rotulo": None})
        self.assertEqual(termo, "PRF")
        self.assertIsNone(ids)

    def test_tipo_ids_usa_rotulo_como_termo(self):
        u = "42f74fb0-3e13-4812-a499-5e7652a06331"
        termo, ids = worker_coleta.pedido_para_coleta(
            {"tipo": "ids", "alvo": u, "rotulo": "Meu Concurso"})
        self.assertEqual(termo, "Meu Concurso")
        self.assertEqual(ids, [u])

    def test_ids_sem_rotulo_erro(self):
        # extrator_ldi.falha() levanta SystemExit (padrão do projeto)
        with self.assertRaises(SystemExit):
            worker_coleta.pedido_para_coleta(
                {"tipo": "ids", "alvo": "x", "rotulo": None})

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest tests.test_worker_coleta -v` → FAIL.

- [ ] **Step 3: Implementar** — `worker_coleta.py`:
```python
# -*- coding: utf-8 -*-
"""
============================================================
 WORKER DE COLETA — roda no VPS (systemd). Observa a fila
 coleta_pedido no Supabase, executa coletor_ldi.coletar()
 (que publica o snapshot no fim), reporta status/progresso,
 honra cancelamento e avisa por e-mail (Resend) quando o
 cookie do LDI cai. Spec: docs/superpowers/specs/2026-07-20-*.
 Uso: py worker_coleta.py   (laço; Ctrl-C encerra)
============================================================
"""
import os
import sys
import time
from datetime import datetime, timezone

import requests

import extrator_ldi
import coletor_ldi
import cookie_status
import sync_supabase

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INTERVALO = 20          # segundos entre ciclos
BANCO = os.path.join(extrator_ldi.PASTA_APP, "saida", "conteudo.db")


def pedido_para_coleta(row):
    """Deriva (termo, ids) de uma linha da fila. termo=rótulo quando tipo=ids."""
    if row["tipo"] == "ids":
        if not row.get("rotulo"):
            raise extrator_ldi.falha("pedido tipo=ids sem rótulo.")
        return row["rotulo"], coletor_ldi.extrair_ids(row["alvo"])
    return row["alvo"], None


def _rest():
    url, key = sync_supabase._config()
    return f"{url}/rest/v1", key


def _patch_pedido(rest, key, pedido_id, campos):
    requests.patch(f"{rest}/coleta_pedido", headers=sync_supabase._headers(key),
                   params={"id": f"eq.{pedido_id}"}, json=campos, timeout=30
                   ).raise_for_status()


def _status_pedido(rest, key, pedido_id):
    r = requests.get(f"{rest}/coleta_pedido", headers=sync_supabase._headers(key),
                     params={"id": f"eq.{pedido_id}", "select": "status"}, timeout=30)
    r.raise_for_status()
    linhas = r.json()
    return linhas[0]["status"] if linhas else None


def _ler_cookie(rest, key):
    r = requests.get(f"{rest}/config_ldi", headers=sync_supabase._headers(key),
                     params={"id": "eq.1", "select": "cookie"}, timeout=30)
    r.raise_for_status()
    linhas = r.json()
    return (linhas[0]["cookie"] if linhas else None) or None


def _publicar_cookie_status(rest, key, cookie):
    r = cookie_status.resumo_validade(cookie or "")
    corpo = {"id": 1, **r, "atualizado_em": datetime.now(timezone.utc).isoformat()}
    requests.post(f"{rest}/cookie_status",
                  headers=sync_supabase._headers(key, "resolution=merge-duplicates"),
                  params={"on_conflict": "id"}, json=corpo, timeout=30).raise_for_status()
    return r


def enviar_email_cookie(assunto, corpo_html):
    """Avisa o admin por e-mail (Resend). Sem RESEND_API_KEY, apenas loga."""
    cfg = sync_supabase._config_json() if hasattr(sync_supabase, "_config_json") else {}
    api = os.environ.get("RESEND_API_KEY") or cfg.get("resend_api_key")
    para = os.environ.get("ADMIN_EMAIL") or cfg.get("admin_email")
    if not api or not para:
        print(f"[worker] (sem Resend/admin_email — não enviei) {assunto}")
        return
    requests.post("https://api.resend.com/emails",
                  headers={"Authorization": f"Bearer {api}", "Content-Type": "application/json"},
                  json={"from": "Painel de Conteúdo <painel@infosab.com.br>",
                        "to": [para], "subject": assunto, "html": corpo_html},
                  timeout=30)


def processar_pedido(rest, key, row, cfg):
    """Executa um pedido; devolve o status final."""
    pid = row["id"]
    _patch_pedido(rest, key, pid, {"status": "rodando",
                                   "iniciado_em": datetime.now(timezone.utc).isoformat()})
    cookie = _ler_cookie(rest, key)
    if not cookie or not cookie_status.resumo_validade(cookie)["valido"]:
        _patch_pedido(rest, key, pid, {"status": "aguardando_cookie",
                                       "mensagem": "cookie ausente ou vencido"})
        enviar_email_cookie("Cookie do LDI precisa ser renovado",
                            "<p>Uma coleta ficou esperando: o cookie do LDI está ausente ou vencido. "
                            "Atualize-o na tela de admin do painel.</p>")
        return "aguardando_cookie"

    def progresso(feito, total):
        _patch_pedido(rest, key, pid, {"progresso": f"{feito}/{total} aulas"})
        if _status_pedido(rest, key, pid) == "cancelando":
            raise coletor_ldi.ColetaCancelada()

    try:
        # dentro do try: um pedido malformado (extrator_ldi.falha=SystemExit)
        # vira status 'erro' em vez de derrubar o worker.
        termo, ids = pedido_para_coleta(row)
        sessao = extrator_ldi.montar_sessao(cfg, cookie)
        extracao_id = coletor_ldi.coletar(cfg, sessao, termo, BANCO,
                                          ids=ids, progresso=progresso)
    except coletor_ldi.ColetaCancelada:
        _patch_pedido(rest, key, pid, {"status": "cancelada",
                                       "concluido_em": datetime.now(timezone.utc).isoformat()})
        return "cancelada"
    except extrator_ldi.CookieVencido as e:
        _patch_pedido(rest, key, pid, {"status": "aguardando_cookie", "mensagem": str(e)[:400]})
        _publicar_cookie_status(rest, key, cookie)  # provavelmente valido=false após probe futuro
        enviar_email_cookie("Cookie do LDI caiu durante a coleta",
                            "<p>A coleta falhou com 401/403 — o cookie do LDI caiu. "
                            "Renove-o na tela de admin e use \"retentar\".</p>")
        return "aguardando_cookie"
    except SystemExit as e:  # falhas do extrator (extrator_ldi.falha) chegam como SystemExit
        _patch_pedido(rest, key, pid, {"status": "erro", "mensagem": str(e)[:400]})
        return "erro"
    except Exception as e:
        _patch_pedido(rest, key, pid, {"status": "erro", "mensagem": str(e)[:400]})
        return "erro"

    _patch_pedido(rest, key, pid, {"status": "concluida", "extracao_id": extracao_id,
                                   "concluido_em": datetime.now(timezone.utc).isoformat()})
    return "concluida"


def main():
    cfg = extrator_ldi.carregar_config()
    rest, key = _rest()
    print(f"[worker] no ar. fila: {rest}/coleta_pedido  |  banco: {BANCO}")
    while True:
        try:
            cookie = _ler_cookie(rest, key)
            _publicar_cookie_status(rest, key, cookie)
            r = requests.get(f"{rest}/coleta_pedido", headers=sync_supabase._headers(key),
                             params={"status": "eq.pendente", "order": "criado_em.asc",
                                     "limit": "1", "select": "*"}, timeout=30)
            r.raise_for_status()
            fila = r.json()
            if fila:
                row = fila[0]
                print(f"[worker] pedido #{row['id']} ({row['tipo']}: {row['alvo'][:40]})")
                status = processar_pedido(rest, key, row, cfg)
                print(f"[worker] pedido #{row['id']} -> {status}")
                continue  # busca o próximo já
        except Exception as e:
            print(f"[worker] ciclo falhou (segue): {e}")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: `_config_json` helper em `sync_supabase.py`** (para o worker ler resend_api_key/admin_email do supabase.json sem duplicar leitura). Adicionar em `sync_supabase.py`:
```python
def _config_json():
    """Lê o supabase.json (se existir) como dict — para campos extra (resend, admin)."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabase.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return {}
```

- [ ] **Step 5: Rodar** — `py -m unittest tests.test_worker_coleta -v` → PASS; suíte inteira verde. (O laço/I/O é validado manualmente na Task 5; os testes cobrem a parte pura.)

- [ ] **Step 6: Commit** — `git add worker_coleta.py sync_supabase.py tests/test_worker_coleta.py && git commit -m "feat: worker de coleta (observa a fila, roda coletor, avisa cookie)"`

---

### Task 5: Deploy no VPS + aceite (hands-on com o Luiz)

**Files:** Create `deploy/worker-coleta.service` (unit systemd); Create `deploy/README-vps.md` (passo a passo).

**Interfaces:** Consome tudo das Tasks 1–4.

- [ ] **Step 1: Unit systemd** — `deploy/worker-coleta.service`:
```ini
[Unit]
Description=Worker de coleta LDI (Painel de Conteudo)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/extrator-ldi
ExecStart=/usr/bin/python3 worker_coleta.py
Restart=always
RestartSec=10
User=extrator

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Passo a passo do VPS** — `deploy/README-vps.md` com: instalar `python3`/`pip`/`git`; clonar o repo em `/opt/extrator-ldi`; `pip install requests`; criar `supabase.json` no servidor com `{url, service_key, resend_api_key, admin_email}`; criar `config.json` (vertical `concursos`, concorrencia 4, pasta_saida `saida`); gravar o cookie inicial em `config_ldi` (script `py -c` que faz o PATCH); copiar a unit para `/etc/systemd/system/`, `systemctl enable --now worker-coleta`; `journalctl -u worker-coleta -f` para acompanhar.

- [ ] **Step 3: Aceite (com o Luiz, no VPS)** — executar os critérios do spec:
  1. Worker sobe; `cookie_status` atualiza no Supabase.
  2. Gravar o cookie válido em `config_ldi`; `cookie_status.valido=true`.
  3. Enfileirar (por SQL/script) um `tipo=ids` com 1 UUID + rótulo → `concluida` + concurso aparece no seletor do app (paridade vs. painel local).
  4. Enfileirar e marcar `cancelando` no meio → `cancelada`; retomar depois funciona.
  5. Pôr um cookie inválido → `aguardando_cookie` + `cookie_status.valido=false` + e-mail chega; "retentar" (status→`pendente`) reprocessa após renovar.
  6. Coleta local por comando (BACEN/PRF/por-ID) segue intacta.

- [ ] **Step 4: Commit** — `git add deploy/ && git commit -m "docs: unit systemd + passo a passo do worker no VPS"`

---

## Self-review
- **Cobertura do spec:** 3 tabelas+RLS ✓ (T1) · worker/laço/status ✓ (T4) · cookie de config_ldi ✓ (T4) · cookie_status ✓ (T2/T4) · e-mail Resend no 401/vencido ✓ (T4) · callback progresso+cancelamento ✓ (T3) · systemd/deploy ✓ (T5) · segurança config_ldi (sem policy authenticated) ✓ (T1) · não-regressão (suíte verde) ✓.
- **Tipos consistentes:** `pedido_para_coleta`, `resumo_validade`, `ColetaCancelada`, `coletar(...progresso=)`, `_baixar_lote(...progresso=)` usados iguais entre tasks.
- **Placeholders:** nenhum — código verbatim em cada passo.
- **Nota:** Tasks 1–4 são construíveis/testáveis na máquina local (mocks; a T1 aplica no Supabase real). A T5 é hands-on no VPS com o Luiz (SSH), como combinado.
