/**
 * ============================================================
 *  EXTRATOR LDI — Vídeos por curso (SOMENTE LEITURA)
 * ============================================================
 *  O que faz:
 *   1. Busca os cursos no LDI pelo termo configurado (ex.: PRF)
 *   2. Varre a árvore de conteúdo de cada curso (capítulos > aulas)
 *   3. Para cada aula que tem vídeo, baixa os blocos e extrai:
 *      ID do vídeo, nome, nome original (legado), intra_video_id,
 *      duração, data de criação, tamanho do arquivo
 *   4. Baixa automaticamente um CSV (Excel pt-BR) e um JSON
 *
 *  Como usar:
 *   1. Abra https://admin.estrategia.com (logado)
 *   2. F12 -> aba "Console"
 *   3. Cole este arquivo inteiro e aperte Enter
 *   4. Aguarde — os arquivos caem na pasta Downloads
 *
 *  Ele NÃO altera nada: só faz requisições GET (leitura).
 * ============================================================
 */
(async () => {
  // ==================== CONFIGURAÇÃO =========================
  const TERMO_BUSCA   = 'PRF';        // termo enviado à busca de cursos da API
  const FILTRO_LOCAL  = null;         // opcional: regex p/ manter só cursos cujo NOME bate.
                                      // Ex.: /PRF|Rodovi/i  (null = mantém tudo que a busca trouxe)
  const VERTICAL      = 'concursos';  // vertical do admin
  const TIPOS_VIDEO   = ['videoMyDocuments', 'cast', 'youtube']; // tipos de bloco considerados vídeo
  const CONCORRENCIA  = 4;            // requisições simultâneas (não exagerar)
  const INCLUIR_URL   = true;         // incluir coluna com a URL do arquivo de vídeo
  // ===========================================================

  const API = 'https://api.estrategia.com';
  const H   = { 'x-vertical': VERTICAL };

  // GET com nova tentativa automática em erro temporário (429/5xx/rede)
  async function getJSON(url, tentativa = 1) {
    try {
      const r = await fetch(url, { credentials: 'include', headers: H });
      if (r.status === 429 || r.status >= 500) throw new Error('HTTP ' + r.status);
      if (!r.ok) { const e = new Error('HTTP ' + r.status); e.fatal = true; throw e; }
      return await r.json();
    } catch (e) {
      if (!e.fatal && tentativa < 4) {
        await new Promise(s => setTimeout(s, 700 * tentativa * tentativa));
        return getJSON(url, tentativa + 1);
      }
      throw e;
    }
  }

  // "01:06:53.80" -> 4014 (segundos)
  function segundos(dur) {
    if (!dur || typeof dur !== 'string') return '';
    const m = dur.match(/(\d+):(\d+):(\d+(?:\.\d+)?)/);
    if (!m) return '';
    return Math.round(+m[1] * 3600 + +m[2] * 60 + +m[3]);
  }

  // ---------- 1) Listagem de cursos ----------
  console.log(`%c🔎 Buscando cursos com "${TERMO_BUSCA}"...`, 'font-weight:bold');
  let cursos = [];
  for (let page = 1; page <= 50; page++) {
    const j = await getJSON(`${API}/bo/ldi/courses?page=${page}&per_page=100&sort=desc&order_by=created_at&include_authors_names=true&search_term=${encodeURIComponent(TERMO_BUSCA)}`);
    const lote = j.data || [];
    cursos.push(...lote);
    if (lote.length < 100) break;
  }
  if (FILTRO_LOCAL) cursos = cursos.filter(c => FILTRO_LOCAL.test(c.name || ''));
  console.log(`📚 ${cursos.length} cursos encontrados.`);
  if (!cursos.length) { console.warn('Nada encontrado — confira o TERMO_BUSCA.'); return; }

  // ---------- 2) Aulas com vídeo (via cache da árvore de conteúdo) ----------
  const tarefas = [];
  for (const curso of cursos) {
    for (const cap of (curso.content_tree_cache || [])) {
      for (const item of (cap.items || [])) {
        const btc = Object.assign({}, item.simple_block_type_count, item.block_type_count);
        if (TIPOS_VIDEO.some(t => btc[t])) tarefas.push({ curso, cap, item });
      }
    }
  }
  console.log(`🎬 ${tarefas.length} aulas com vídeo para inspecionar (1 requisição por aula)...`);

  // ---------- 3) Blocos de cada aula ----------
  // Aulas compartilhadas entre cursos são baixadas uma única vez (cache).
  const cacheBlocos = new Map();
  function blocosDoItem(itemId) {
    if (!cacheBlocos.has(itemId)) {
      cacheBlocos.set(itemId, getJSON(`${API}/bo/ldi/blocks?item_id=${itemId}`).then(j => j.data || []));
    }
    return cacheBlocos.get(itemId);
  }

  function linha(curso, cap, item, bloco, erro) {
    const d   = (bloco && bloco.data) || {};
    const res = d.resolved || (bloco && bloco.simple_data && bloco.simple_data.resolved) || {};
    return {
      curso_id:            curso.id,
      curso_nome:          curso.name || '',
      curso_publicado:     curso.published ? 'sim' : 'nao',
      curso_criado_em:     curso.created_at || '',
      professores:         curso.authors_name || (curso.authors || []).map(a => a.name || a).join(' | ') || '',
      capitulo_ordem:      (cap.order_index ?? '') === '' ? '' : cap.order_index + 1,
      capitulo_nome:       cap.name || '',
      capitulo_versao:     cap.chapter_version ?? '',
      capitulo_publicado:  cap.published_at || '',
      capitulo_id:         cap.chapter_id || '',
      aula_path:           item.path || '',
      aula_nome:           item.name || item.title || '',
      aula_atualizada_em:  item.updated_at || '',
      item_id:             item.item_id || '',
      bloco_tipo:          bloco ? bloco.type : '',
      bloco_id:            bloco ? bloco.id : '',
      bloco_ordem:         bloco ? bloco.order_index : '',
      bloco_rascunho:      bloco ? (bloco.is_draft ? 'sim' : 'nao') : '',
      bloco_criado_em:     bloco ? (bloco.created_at || '') : '',
      bloco_atualizado_em: bloco ? (bloco.updated_at || '') : '',
      video_id:            res.id ?? d.videoId ?? (bloco && bloco.content_id) ?? '',
      video_nome:          res.name || res.title || '',
      video_nome_original: res.original_name || '',
      video_intra_id:      res.intra_video_id || '',
      video_duracao:       res.video_duration || res.duration || '',
      video_duracao_seg:   segundos(res.video_duration || res.duration),
      video_criado_em:     res.created_at || '',
      video_tamanho_bytes: res.file_size ?? '',
      video_url:           INCLUIR_URL ? (typeof res.data === 'string' ? res.data : (res.url || '')) : '',
      erro:                erro || ''
    };
  }

  const linhas = [];
  let feitos = 0, falhas = 0;
  const fila = tarefas.slice();
  async function operario() {
    while (fila.length) {
      const t = fila.shift();
      try {
        const blocos = await blocosDoItem(t.item.item_id);
        let achou = false;
        for (const b of blocos) {
          if (!TIPOS_VIDEO.includes(b.type)) continue;
          linhas.push(linha(t.curso, t.cap, t.item, b, ''));
          achou = true;
        }
        // aula marcada com vídeo no cache mas sem bloco de vídeo publicado -> registra mesmo assim
        if (!achou) linhas.push(linha(t.curso, t.cap, t.item, null, 'aula sem bloco de video na versao atual'));
      } catch (e) {
        falhas++;
        linhas.push(linha(t.curso, t.cap, t.item, null, 'ERRO: ' + e.message));
      }
      feitos++;
      if (feitos % 100 === 0) console.log(`   ...${feitos}/${tarefas.length} aulas processadas`);
    }
  }
  await Promise.all(Array.from({ length: CONCORRENCIA }, operario));

  // ---------- 4) Ordena e exporta ----------
  const pathNum = p => String(p || '').split('.').map(n => String(n).padStart(4, '0')).join('.');
  linhas.sort((a, b) =>
    a.curso_nome.localeCompare(b.curso_nome) ||
    (a.capitulo_ordem || 0) - (b.capitulo_ordem || 0) ||
    pathNum(a.aula_path).localeCompare(pathNum(b.aula_path)) ||
    (a.bloco_ordem || 0) - (b.bloco_ordem || 0));

  const colunas = Object.keys(linhas[0]);
  const esc = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  // BOM (\uFEFF) + ponto e vírgula -> abre certo no Excel pt-BR, sem mojibake
  const csv = '\uFEFF' + [colunas.join(';'), ...linhas.map(l => colunas.map(c => esc(l[c])).join(';'))].join('\r\n');

  const dataStr = new Date().toISOString().slice(0, 10);
  function baixa(conteudo, nome, tipo) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
    a.download = nome;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  baixa(csv, `videos_${TERMO_BUSCA}_${dataStr}.csv`, 'text/csv;charset=utf-8');
  baixa(JSON.stringify(linhas, null, 1), `videos_${TERMO_BUSCA}_${dataStr}.json`, 'application/json');

  console.log(`%c✅ Pronto! ${linhas.length} linhas de vídeo | ${cursos.length} cursos | falhas: ${falhas}`, 'color:green;font-weight:bold');
  console.log('📥 Arquivos baixados na pasta Downloads (CSV para Excel + JSON).');
  console.table(linhas.slice(0, 5));
  window.__videosExtraidos = linhas; // fica disponível no console se quiser mexer mais
})();
