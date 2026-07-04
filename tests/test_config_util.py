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
