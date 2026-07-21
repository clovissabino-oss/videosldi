import unittest
import base64
import json
import time
from unittest.mock import patch, MagicMock

import worker_coleta
import coletor_ldi

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


def _cookie_valido():
    """Cria um JWT válido (cookie __Secure-SID) com expiração em 5 dias."""
    exp = int(time.time()) + 5 * 86400
    payload = {"email": "test@example.com", "exp": exp}
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"__Secure-SID=x.{p}.y"


class TestProcessarPedidoCookie(unittest.TestCase):
    """Testa o comportamento quando o cookie cai durante a coleta."""

    @patch("worker_coleta.enviar_email_cookie")
    @patch("worker_coleta._publicar_cookie_status")
    @patch("worker_coleta.coletor_ldi.coletar", side_effect=coletor_ldi.CookieVencido("401"))
    @patch("worker_coleta.extrator_ldi.montar_sessao")
    @patch("worker_coleta._ler_cookie")
    @patch("worker_coleta._patch_pedido")
    def test_cookie_cai_durante_coleta_vira_aguardando(
        self, mock_patch, mock_ler_cookie, mock_sessao, mock_coletar,
        mock_publicar_status, mock_enviar_email
    ):
        """Quando CookieVencido é levantado durante coletar(), status vira aguardando_cookie."""
        mock_ler_cookie.return_value = _cookie_valido()
        mock_sessao.return_value = MagicMock()

        row = {"id": 42, "tipo": "termo", "alvo": "PRF", "rotulo": None}
        cfg = {"vertical": "concursos"}
        rest, key = "http://mock", "mock_key"

        status = worker_coleta.processar_pedido(rest, key, row, cfg)

        # Verificar que o status foi alterado para aguardando_cookie
        self.assertEqual(status, "aguardando_cookie")

        # Verificar que o pedido foi patchado com status=aguardando_cookie
        patch_call_args = mock_patch.call_args_list
        # Primeira chamada: status="rodando"
        # Segunda chamada: status="aguardando_cookie"
        aguardando_call = [c for c in patch_call_args
                          if c[0][2] and "status" in c[0][3]
                          and c[0][3].get("status") == "aguardando_cookie"]
        self.assertTrue(aguardando_call, "esperava patch com status=aguardando_cookie")

        # Verificar que enviar_email_cookie foi chamado (aviso de cookie caiu)
        mock_enviar_email.assert_called_once()
        call_args = mock_enviar_email.call_args
        self.assertIn("cookie", call_args[0][0].lower())

        # Verificar que o cookie status foi publicado
        mock_publicar_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
