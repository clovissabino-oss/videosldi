# Coleta por ID do LDI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development ou superpowers:executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Permitir coletar um ou mais cursos pelo **ID do LDI** (UUID), agrupados sob um **rótulo** que vira o concurso no app — além da coleta por termo de busca que já existe.

**Contexto/decisões (Fase 2 do roteiro; spike já feito em 20/07):** `GET /bo/ldi/courses/{id}`
**devolve `content_tree_cache` completo** → coletar por ID reusa 100% do pipeline atual.
Não há campo de concurso no payload → quem dispara informa um **rótulo** (`--rotulo`), e
uma ou mais **`--ids`** entram num único snapshot sob esse rótulo (decisão do Luiz: "rótulo +
lista de IDs = um concurso"; sem risco de sobrescrever concursos coletados por termo, porque
é um snapshot completo por rodada, igual à coleta por termo). Roda local, como hoje.

**Tech stack:** Python 3.12, `requests`, `unittest` (NÃO pytest). Idioma pt-BR.

## Global Constraints
- Não regredir a coleta por termo nem o sync — só adicionar o caminho por ID.
- Reusar `extrator_ldi.get_json` (trata 401/cookie e retry) — não fazer `sessao.get` cru novo.
- Extração de ID deve pegar o `id=` da URL do admin, **nunca** o `team_id=`.
- Testes em `unittest`, seguindo o estilo de `tests/test_coletor.py`.

---

### Task 1: `extrator_ldi.obter_curso(sessao, curso_id)`

**Files:** Modify `extrator_ldi.py` (logo após `listar_cursos`, ~linha 139); Test `tests/test_extrator_id.py` (novo).

**Interfaces:**
- Produces: `obter_curso(sessao, curso_id) -> dict | None` — o dict do curso no mesmo formato de um item de `listar_cursos` (tem `id`, `name`, `content_tree_cache`, `structured_authors`).

- [ ] **Step 1: Teste que falha** — `tests/test_extrator_id.py`:
```python
import unittest
from unittest.mock import MagicMock
import extrator_ldi

class TestObterCurso(unittest.TestCase):
    def _sessao(self, payload, status=200):
        s = MagicMock()
        resp = MagicMock(status_code=status, ok=(status == 200))
        resp.json.return_value = payload
        s.get.return_value = resp
        return s

    def test_devolve_curso_com_arvore(self):
        curso = {"id": "42f7-uuid", "name": "Curso X",
                 "content_tree_cache": [{"chapter_id": "c1", "items": [{"item_id": "i1"}]}]}
        s = self._sessao({"data": curso})
        r = extrator_ldi.obter_curso(s, "42f7-uuid")
        self.assertEqual(r["id"], "42f7-uuid")
        self.assertIn("content_tree_cache", r)
        # usou o endpoint por ID
        self.assertIn("/bo/ldi/courses/42f7-uuid", s.get.call_args[0][0])

    def test_data_vazio_vira_none(self):
        s = self._sessao({"data": None})
        self.assertIsNone(extrator_ldi.obter_curso(s, "x"))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest tests.test_extrator_id -v` → FAIL (obter_curso não existe).

- [ ] **Step 3: Implementar** — em `extrator_ldi.py`, logo após `listar_cursos`:
```python
def obter_curso(sessao, curso_id):
    """Detalhe de um curso pelo ID (UUID). O payload já traz content_tree_cache
    (capítulos→aulas) e structured_authors — mesmo formato de um item de
    listar_cursos. Devolve o dict do curso, ou None se a API não trouxer dados."""
    dados = get_json(sessao, f"{API}/bo/ldi/courses/{curso_id}").get("data")
    return dados or None
```

- [ ] **Step 4: Rodar e ver passar** — `py -m unittest tests.test_extrator_id -v` → PASS.

- [ ] **Step 5: Commit** — `git add extrator_ldi.py tests/test_extrator_id.py && git commit -m "feat: extrator obtém curso por ID (reusa content_tree_cache do detalhe)"`

---

### Task 2: `coletor_ldi.extrair_ids` + coleta por IDs em `coletar` + CLI

**Files:** Modify `coletor_ldi.py`; Test `tests/test_coletor_id.py` (novo).

**Interfaces:**
- Consumes: `extrator_ldi.obter_curso` (Task 1).
- Produces: `extrair_ids(texto) -> list[str]`; `coletar(..., ids=None)` (novo kwarg opcional); CLI `--ids`/`--rotulo`.

- [ ] **Step 1: Teste que falha** — `tests/test_coletor_id.py`:
```python
import unittest
import coletor_ldi

class TestExtrairIds(unittest.TestCase):
    def test_uuid_solto(self):
        u = "42f74fb0-3e13-4812-a499-5e7652a06331"
        self.assertEqual(coletor_ldi.extrair_ids(u), [u])

    def test_url_admin_pega_id_nao_team_id(self):
        u = ("https://admin.estrategia.com/#/concursos/livros-digitais-interativos/"
             "courses/view?id=42f74fb0-3e13-4812-a499-5e7652a06331"
             "&team_id=6e3c5198-9481-4b73-842e-89c283510889")
        self.assertEqual(coletor_ldi.extrair_ids(u),
                         ["42f74fb0-3e13-4812-a499-5e7652a06331"])

    def test_varios_separadores_e_caixa(self):
        r = coletor_ldi.extrair_ids(
            "42F74FB0-3E13-4812-A499-5E7652A06331, "
            "6e3c5198-9481-4b73-842e-89c283510889")
        self.assertEqual(r, ["42f74fb0-3e13-4812-a499-5e7652a06331",
                             "6e3c5198-9481-4b73-842e-89c283510889"])

    def test_invalido_levanta(self):
        with self.assertRaises(SystemExit):
            coletor_ldi.extrair_ids("isso não tem id")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e ver falhar** — `py -m unittest tests.test_coletor_id -v` → FAIL.

- [ ] **Step 3: Implementar `extrair_ids`** — em `coletor_ldi.py` (perto do topo, após os imports):
```python
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

def extrair_ids(texto):
    """Aceita UUIDs soltos e/ou URLs do admin (…?id=<uuid>&team_id=…),
    separados por vírgula/espaço/linha. Pega SEMPRE o id= (nunca o team_id=).
    Devolve a lista de UUIDs em minúsculas; levanta se algum token não tiver ID."""
    ids = []
    for tok in re.split(r"[\s,]+", (texto or "").strip()):
        if not tok:
            continue
        m = re.search(rf"[?&]id=({_UUID})", tok)
        if m:
            ids.append(m.group(1).lower())
        elif re.fullmatch(_UUID, tok):
            ids.append(tok.lower())
        else:
            raise extrator_ldi.falha(f"Não achei um ID de curso em: {tok[:60]}")
    if not ids:
        raise extrator_ldi.falha("Nenhum ID de curso informado.")
    return ids
```

- [ ] **Step 4: Coleta por IDs em `coletar`** — assinatura ganha `ids=None`:
DE:
```python
def coletar(cfg, sessao, termo, caminho_banco, continuar=False, com_videos=False):
```
PARA:
```python
def coletar(cfg, sessao, termo, caminho_banco, continuar=False, com_videos=False, ids=None):
```
E o bloco do `else:` (busca de cursos) — DE:
```python
        else:
            print(f"[1/4] Buscando cursos com \"{termo}\"...")
            cursos = extrator_ldi.listar_cursos(sessao, termo)
            if cfg.get("filtro_local"):
                rx = re.compile(cfg["filtro_local"], re.I)
                cursos = [c for c in cursos if rx.search(c.get("name") or "")]
            if not cursos:
                raise extrator_ldi.falha("Nenhum curso encontrado — confira o termo.")
            extracao_id = banco_conteudo.iniciar_extracao(con, termo, cfg["vertical"])
```
PARA:
```python
        else:
            if ids:
                print(f"[1/4] Buscando {len(ids)} curso(s) por ID (rótulo \"{termo}\")...")
                cursos = [c for c in (extrator_ldi.obter_curso(sessao, i) for i in ids) if c]
                if not cursos:
                    raise extrator_ldi.falha("Nenhum curso encontrado para as IDs informadas.")
            else:
                print(f"[1/4] Buscando cursos com \"{termo}\"...")
                cursos = extrator_ldi.listar_cursos(sessao, termo)
                if cfg.get("filtro_local"):
                    rx = re.compile(cfg["filtro_local"], re.I)
                    cursos = [c for c in cursos if rx.search(c.get("name") or "")]
                if not cursos:
                    raise extrator_ldi.falha("Nenhum curso encontrado — confira o termo.")
            extracao_id = banco_conteudo.iniciar_extracao(con, termo, cfg["vertical"])
```
(o restante da função — gravar_arvore, _completar_autores, blocos, qualidade, sync — não muda.)

- [ ] **Step 5: CLI** — em `main()`, adicionar os argumentos (após `--termo`):
```python
    parser.add_argument("--ids", help="coleta cursos por ID do LDI (UUIDs ou URLs do admin, "
                                      "separados por vírgula/espaço); exige --rotulo")
    parser.add_argument("--rotulo", help="nome do concurso sob o qual as --ids aparecem no "
                                         "app (vira o 'termo' do snapshot)")
```
E trocar a resolução de `termo` + a chamada. DE:
```python
    cfg = extrator_ldi.carregar_config()
    termo = args.termo or cfg["termo_busca"]
    if args.continuar and args.com_videos:
        raise extrator_ldi.falha("--com-videos não funciona com --continuar "
                                 "(rode uma coleta nova).")
```
PARA:
```python
    cfg = extrator_ldi.carregar_config()
    if args.continuar and args.com_videos:
        raise extrator_ldi.falha("--com-videos não funciona com --continuar "
                                 "(rode uma coleta nova).")
    if args.ids:
        if not args.rotulo:
            raise extrator_ldi.falha("--ids exige --rotulo (o nome do concurso no app).")
        if args.continuar:
            raise extrator_ldi.falha("--ids não combina com --continuar "
                                     "(para retomar, use --termo \"<rótulo>\" --continuar).")
        ids = extrair_ids(args.ids)
        termo = args.rotulo
    else:
        ids = None
        termo = args.termo or cfg["termo_busca"]
```
E a chamada de `coletar`. DE:
```python
    coletar(cfg, sessao, termo, caminho,
            continuar=args.continuar, com_videos=args.com_videos)
```
PARA:
```python
    coletar(cfg, sessao, termo, caminho,
            continuar=args.continuar, com_videos=args.com_videos, ids=ids)
```

- [ ] **Step 6: Rodar testes** — `py -m unittest tests.test_coletor_id -v` → PASS; e a suíte inteira `py -m unittest discover -s tests` → tudo verde (garante que a coleta por termo não regrediu).

- [ ] **Step 7: `py coletor_ldi.py --help`** deve listar `--ids` e `--rotulo` sem erro.

- [ ] **Step 8: Commit** — `git add coletor_ldi.py tests/test_coletor_id.py && git commit -m "feat: coletor aceita --ids + --rotulo (coleta por ID do LDI num snapshot)"`

---

## Self-review
- Cobertura: obter_curso ✓ (T1) · extrair_ids com trap do team_id ✓ (T2) · coleta por IDs reusa pipeline ✓ (T2 Step 4) · CLI ✓ (T2 Step 5) · não regride termo (suíte verde) ✓.
- Verificação end-to-end fica para o controlador: rodar `py coletor_ldi.py --ids <uuid real> --rotulo "Teste ID"` com cookie válido e conferir o snapshot no Supabase + o rótulo no seletor do app.
