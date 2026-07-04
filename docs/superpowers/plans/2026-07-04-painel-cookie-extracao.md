# Painel "Colar cookie e extrair" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o popover do cookie do Visualizador LDI num ponto de partida único: colar o cookie do F12, escolher o concurso e, num clique, salvar + validar + extrair do zero + abrir a árvore de vídeos.

**Architecture:** Reaproveita os endpoints Flask que já existem (`/api/cookie`, `/api/extrair`, `/api/extrair/status`, `/api/dados`) e a UI de progresso da extração já presente na `ui.html`. As duas mudanças de backend são pequenas: `/api/cookie` passa a persistir o concurso no `config.json`, e o status do cookie passa a devolver o concurso atual. A lógica de gravação do `config.json` é isolada num módulo próprio para ser testável sem rede. O frontend funde os passos "salvar cookie" e "extrair" num só botão, reutilizando `acompanharExtracao()`.

**Tech Stack:** Python 3.12, Flask, `requests` (já presentes). Testes com `unittest` da biblioteca padrão (zero dependência nova). Frontend em JS vanilla inline na `ui.html`.

## Global Constraints

- Idioma de todo código, comentário, UI e mensagem: **pt-BR**.
- **Sem dependências novas** — só `requests` + `flask`. Testes usam `unittest` (stdlib).
- **Metabase intacto:** não alterar `depara_metabase.py` nem o caminho de auth do Metabase; nesta fase ele fica apenas oculto na UI (uma nota "em breve").
- **Segurança dos testes:** nenhum teste automatizado pode escrever no `cookie.txt` ou no `config.json` reais da pasta do app — sob risco de apagar a credencial ativa do usuário. Testes de arquivo usam sempre um diretório temporário.
- **Reempacotar o `.exe`:** após mexer em `ui.html` ou `visualizador.py`, reempacotar o `VisualizadorLDI.exe` (a UI vai embutida via `--add-data`), senão o executável serve a versão antiga.
- CSV/JSON de saída e caches permanecem como estão; extração sempre grava em `saida/`.

## File Structure

- `config_util.py` **(criar)** — leitura/gravação isolada do `config.json`. Uma responsabilidade: persistir o `termo_busca` preservando as demais chaves. Sem Flask, sem `requests` → testável em isolamento.
- `tests/test_config_util.py` **(criar)** — testes hermético­s do `config_util` com `tempfile`.
- `visualizador.py` **(modificar)** — importar `config_util`; `/api/cookie` passa a persistir o concurso; `_status_cookie` passa a devolver o concurso atual.
- `ui.html` **(modificar)** — `#modalCookie` vira "Cookie e extração" (campo de concurso + botão "Salvar e extrair" + nota do Metabase); novo `salvarCookieEExtrair()`; refatorar a extração num `dispararExtracao(termo)` reutilizável.
- `PROXIMA-SESSAO.md` **(modificar)** — nota curta da nova sessão para o próximo turno.

---

### Task 1: `config_util.py` — persistir o concurso no config.json

**Files:**
- Create: `config_util.py`
- Test: `tests/test_config_util.py`

**Interfaces:**
- Consumes: nada (stdlib `json`, `os`).
- Produces: `atualizar_termo(caminho_config: str, termo: str) -> str` — atualiza `termo_busca` no JSON indicado preservando as demais chaves; cria o arquivo se não existir; devolve o termo gravado.

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_config_util.py`:

```python
# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config_util


class TestAtualizarTermo(unittest.TestCase):
    def test_atualiza_termo_e_preserva_outras_chaves(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "config.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump({"termo_busca": "PRF", "concorrencia": 4,
                           "vertical": "concursos"}, f)

            devolvido = config_util.atualizar_termo(caminho, "PF")

            self.assertEqual(devolvido, "PF")
            with open(caminho, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            self.assertEqual(cfg["termo_busca"], "PF")
            self.assertEqual(cfg["concorrencia"], 4)
            self.assertEqual(cfg["vertical"], "concursos")

    def test_config_inexistente_e_criado_com_o_termo(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "config.json")

            config_util.atualizar_termo(caminho, "Receita")

            with open(caminho, encoding="utf-8-sig") as f:
                cfg = json.load(f)
            self.assertEqual(cfg["termo_busca"], "Receita")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `py tests/test_config_util.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config_util'`.

- [ ] **Step 3: Implementar o mínimo para passar**

Create `config_util.py`:

```python
# -*- coding: utf-8 -*-
"""Leitura/gravação isolada do config.json.

Fica separado do visualizador.py (Flask/requests) para poder ser testado sem
rede — é aqui que mora a única regra de negócio nova do backend desta fase:
persistir o concurso escolhido na tela.
"""
import json
import os


def atualizar_termo(caminho_config, termo):
    """Atualiza 'termo_busca' no config.json indicado, preservando as demais
    chaves. Se o arquivo não existir, cria um contendo apenas o termo.
    Devolve o termo gravado."""
    cfg = {}
    if os.path.exists(caminho_config):
        with open(caminho_config, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    cfg["termo_busca"] = termo
    with open(caminho_config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return termo
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `py tests/test_config_util.py -v`
Expected: PASS — 2 testes OK.

- [ ] **Step 5: Commit**

```bash
git add config_util.py tests/test_config_util.py
git commit -m "feat: config_util para persistir o concurso (termo_busca) no config.json"
```

---

### Task 2: Backend — `/api/cookie` persiste o concurso e o status o devolve

**Files:**
- Modify: `visualizador.py` (import perto da linha 34; `_status_cookie` linhas ~65-99; `api_cookie_salvar` linhas ~107-117)

**Interfaces:**
- Consumes: `config_util.atualizar_termo(caminho, termo)` (Task 1); helpers existentes `_status_cookie(probar)`, `ex.carregar_config()`, constante `PASTA_APP`.
- Produces:
  - `POST /api/cookie` passa a aceitar corpo `{cookie: str, termo?: str}`; quando `termo` vier não-vazio, grava em `config.json`. Resposta inalterada (o dict de `_status_cookie`).
  - `GET /api/cookie/status` passa a incluir a chave `"termo"` (o `termo_busca` atual, ou `""`).

- [ ] **Step 1: Importar o config_util**

Em `visualizador.py`, logo após `import extrator_ldi as ex` (linha ~34), adicionar:

```python
import config_util
```

- [ ] **Step 2: `_status_cookie` passa a devolver o concurso atual**

No dict `info = {...}` de `_status_cookie` (linhas ~67-75), acrescentar a chave `"termo": ""`:

```python
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
```

(O bloco `try` fica **antes** do `if not info["existe"]: return info`, para que o concurso venha mesmo quando ainda não há cookie.)

- [ ] **Step 3: `api_cookie_salvar` passa a persistir o concurso**

Substituir o corpo de `api_cookie_salvar` (linhas ~107-117) por:

```python
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
```

- [ ] **Step 4: Verificação manual (não há teste automatizado — ver Global Constraints)**

Um teste automatizado deste endpoint escreveria no `cookie.txt`/`config.json` reais, o que é proibido. A lógica de persistência já está coberta pelo teste hermético da Task 1; aqui a mudança é só fiação. Verificar assim, com o servidor rodando **numa cópia de trabalho** (ou aceitando que vai sobrescrever seu `config.json` local de dev):

Run: `py visualizador.py --sem-navegador` (num terminal separado), depois:

```bash
curl -s "http://127.0.0.1:8765/api/cookie/status" | python -c "import sys,json; print('termo=', json.load(sys.stdin).get('termo'))"
```
Expected: imprime `termo= PRF` (ou o concurso atual do seu `config.json`) — confirma que o status agora devolve o concurso. Encerrar o servidor (Ctrl+C).

- [ ] **Step 5: Commit**

```bash
git add visualizador.py
git commit -m "feat: /api/cookie persiste o concurso e /api/cookie/status o devolve"
```

---

### Task 3: Frontend — painel "Cookie e extração" com botão fundido

**Files:**
- Modify: `ui.html` (bloco `#modalCookie` linhas ~352-366; `atualizarStatusCookie` linha ~1939; `iniciarExtracao` linha ~1989; adicionar `dispararExtracao` e `salvarCookieEExtrair`)

**Interfaces:**
- Consumes: `POST /api/cookie` (agora com `{cookie, termo}`), `GET /api/cookie/status` (agora com `termo`), `POST /api/extrair` (`{termo}`), `acompanharExtracao()`, `fecharModais()`, `toast()`, `$()`.
- Produces: fluxo de UI "colar → Salvar e extrair → árvore". Novo `dispararExtracao(termo) -> Promise<boolean>` reutilizado por `iniciarExtracao()` e `salvarCookieEExtrair()`.

- [ ] **Step 1: Reescrever o HTML do `#modalCookie`**

Substituir o bloco `#modalCookie` (linhas ~352-366) por:

```html
<!-- ==================== MODAL COOKIE + EXTRAÇÃO ==================== -->
<div class="veu" id="modalCookie">
  <div class="modal">
    <h2>🔑 Cookie e extração</h2>
    <div class="status-caixa" id="cookieStatusCaixa">Verificando...</div>
    <p style="font-size:13px; margin-bottom:8px"><b>Colar o cookie do admin:</b>
       no Chrome logado no admin → F12 → aba <b>Network</b> → F5 → filtre por
       <code>api.estrategia.com</code> → clique numa linha → <b>Request Headers</b> →
       copie o valor inteiro da linha <code>cookie:</code> e cole abaixo.</p>
    <textarea id="cookieNovo" placeholder="cole aqui o cookie completo..."></textarea>
    <div style="display:flex; gap:10px; align-items:flex-end; margin-top:10px">
      <div style="flex:0 0 160px">
        <label style="font-size:12px; color:var(--texto2); display:block; margin-bottom:4px">Concurso</label>
        <input type="text" id="cookieTermo" placeholder="PRF" style="width:100%">
      </div>
      <div style="flex:1; text-align:right">
        <button class="btn" onclick="fecharModais()">Fechar</button>
        <button class="btn primario" id="btnSalvarExtrair" onclick="salvarCookieEExtrair()">💾 Salvar e extrair</button>
      </div>
    </div>
    <p style="font-size:12px; color:var(--texto2); margin-top:14px; border-top:1px dashed var(--borda); padding-top:10px">
      📊 <b>Metabase</b> (data real de gravação) — em breve; hoje roda pelo <code>_depara_metabase.bat</code>.</p>
  </div>
</div>
```

- [ ] **Step 2: `atualizarStatusCookie` preenche o campo de concurso**

Dentro de `atualizarStatusCookie`, logo depois de setar `$("cookieStatusCaixa").innerHTML = ...` (linha ~1962) e antes do `} catch`, acrescentar:

```javascript
    const campoTermo = $("cookieTermo");
    if (campoTermo && !campoTermo.value.trim() && s.termo) campoTermo.value = s.termo;
```

- [ ] **Step 3: Extrair um `dispararExtracao(termo)` reutilizável e usá-lo em `iniciarExtracao`**

Substituir a função `iniciarExtracao` (linhas ~1989-1996) por estas duas funções:

```javascript
async function dispararExtracao(termo){
  const r = await fetch("/api/extrair", {method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify({termo})});
  if (!r.ok){ const e = await r.json().catch(() => ({})); toast(e.erro || "Erro ao extrair."); return false; }
  $("modalExtrair").classList.add("aberto");
  $("btnIniciarExtracao").disabled = true;
  acompanharExtracao();
  return true;
}
async function iniciarExtracao(){
  await dispararExtracao($("termoExtrair").value.trim());
}
```

- [ ] **Step 4: Adicionar `salvarCookieEExtrair`**

Logo após `salvarCookie` (linha ~1980), adicionar:

```javascript
async function salvarCookieEExtrair(){
  const valor = $("cookieNovo").value.trim();
  const termo = $("cookieTermo").value.trim();
  if (!valor) return toast("Cole o cookie primeiro.");
  if (!termo) return toast("Informe o concurso (ex.: PRF).");
  const btn = $("btnSalvarExtrair");
  btn.disabled = true;
  try {
    const r = await fetch("/api/cookie", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({cookie:valor, termo})});
    const s = await r.json();
    if (!r.ok){ toast(s.erro || "Erro ao salvar."); return; }
    $("cookieNovo").value = "";
    atualizarStatusCookie();
    if (!s.valido){ toast("Cookie salvo, mas a API recusa (HTTP " + (s.http ?? "—") + "). Cole um cookie novo."); return; }
    toast("Cookie ok! Iniciando extração…");
    fecharModais();
    await dispararExtracao(termo);
  } finally {
    btn.disabled = false;
  }
}
```

- [ ] **Step 5: Verificação manual (UI + extração ao vivo)**

Rodar `py visualizador.py` e, na tela:
1. Clicar na pill do cookie → abre o painel **🔑 Cookie e extração** com o campo **Concurso** já preenchido (ex.: `PRF`) e a nota do Metabase no rodapé.
2. **Cookie válido:** colar um cookie bom → "Salvar e extrair" → o painel do cookie fecha, o de progresso abre, a barra anda e ao final a árvore de vídeos carrega sozinha.
3. **Cookie vencido:** colar um cookie ruim → aparece o aviso "a API recusa (HTTP …)" e **não** dispara extração.
4. **Concurso vazio:** apagar o campo Concurso e clicar → toast "Informe o concurso".

- [ ] **Step 6: Commit**

```bash
git add ui.html
git commit -m "feat: painel Cookie e extração — salvar cookie + concurso e extrair num clique"
```

---

### Task 4: Reempacotar o `.exe` e anotar a sessão

**Files:**
- Rebuild: `VisualizadorLDI.exe` (via PyInstaller; artefato — fora do git)
- Modify: `PROXIMA-SESSAO.md`

**Interfaces:** nenhuma (empacotamento + doc).

- [ ] **Step 1: Reempacotar o VisualizadorLDI.exe**

Na pasta do projeto:

```bash
py -m PyInstaller --onefile --clean --name VisualizadorLDI --add-data "ui.html;." --add-data "estoque.html;." visualizador.py
```

Copiar `dist/VisualizadorLDI.exe` para a raiz do projeto, substituindo o antigo.

- [ ] **Step 2: Verificar o executável**

Executar o `VisualizadorLDI.exe` recém-gerado → o navegador abre em `http://127.0.0.1:8765` → confirmar que o painel do cookie mostra o novo título **🔑 Cookie e extração**, o campo Concurso e a nota do Metabase (ou seja, o exe está servindo a `ui.html` nova).

- [ ] **Step 3: Anotar a sessão em PROXIMA-SESSAO.md**

Acrescentar, no topo da lista de sessões de `PROXIMA-SESSAO.md`, um item curto:

```markdown
## ✅ Sessão 4: painel "Cookie e extração" (colar → 1 clique → árvore)

O popover do cookie virou o ponto de partida: cola-se o cookie do F12, escolhe-se
o concurso (campo novo, salvo no config.json via `/api/cookie`) e o botão
**💾 Salvar e extrair** salva, valida, extrai do zero e abre a árvore — reusando a
UI de progresso da extração. Metabase segue oculto na tela (nota "em breve"); o
de→para continua pelo `.bat`. Lógica de persistência do concurso isolada em
`config_util.py` (com teste `unittest`). Rebuild do VisualizadorLDI.exe feito.
Projeto agora versionado em github.com/clovissabino-oss/videosldi.
```

- [ ] **Step 4: Commit**

```bash
git add PROXIMA-SESSAO.md
git commit -m "docs: registra a sessão do painel Cookie e extração"
```

---

## Self-Review

**1. Spec coverage:**
- §2 escopo (colar → salvar → extrair → árvore): Tasks 2+3. ✔
- §2 não-objetivo "Metabase oculto": nota no HTML (Task 3, Step 1) + nenhuma alteração no `depara_metabase.py`. ✔
- §3 decisão "campo de concurso na tela, padrão do config": Task 3 (campo `#cookieTermo` preenchido via `s.termo`). ✔
- §3 decisão "sempre extrair do zero": `salvarCookieEExtrair` sempre chama `dispararExtracao` quando o cookie é válido. ✔
- §5 fluxo salvar→validar→extrair→árvore: Task 3, Step 4 (valida via `s.valido` antes de extrair; `acompanharExtracao` carrega a árvore no fim). ✔
- §6 erros: cookie inválido (400 do endpoint), cookie vencido (`!s.valido` → para), termo vazio (toast), extração falha (tratada por `acompanharExtracao` existente). ✔
- §6 "sem botão só-salvar na v1": o `#modalCookie` tem apenas "Salvar e extrair". ✔
- §7 teste hermético do termo: Task 1. ✔
- §9 arquivos afetados (ui.html, visualizador.py, config.json via tela, rebuild exe): Tasks 2, 3, 4. ✔

**2. Placeholder scan:** sem "TBD"/"TODO"; todos os passos de código trazem o código real. ✔

**3. Type consistency:** `atualizar_termo(caminho, termo)` definido na Task 1 e chamado igual na Task 2. `dispararExtracao(termo)` definido e chamado com a mesma assinatura nas Tasks 3.3/3.4. Chaves de status (`s.termo`, `s.valido`, `s.http`) coerentes com o que `_status_cookie` devolve (Task 2). ✔

Observação de escopo: não há teste automatizado para o endpoint `/api/cookie` nem para a UI, por decisão de segurança (evitar sobrescrever `cookie.txt`/`config.json` reais) e por serem superfícies de rede/UI — cobertos por roteiro manual (Tasks 2.4 e 3.5), como previsto na §7 do spec.
