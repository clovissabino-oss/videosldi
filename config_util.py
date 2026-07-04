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
