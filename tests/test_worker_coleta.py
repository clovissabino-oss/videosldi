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

        # Verificar que o cookie status foi publicado com forcar_invalido=True
        # (o banner não pode aparecer válido quando o cookie foi rejeitado pelo LDI)
        mock_publicar_status.assert_called_once()
        call_args = mock_publicar_status.call_args
        forcar_invalido = call_args.kwargs.get("forcar_invalido")
        if forcar_invalido is None:
            # aceita também posicional (4º argumento)
            forcar_invalido = call_args.args[3] if len(call_args.args) > 3 else None
        self.assertIs(forcar_invalido, True)


class TestProgressoCallback(unittest.TestCase):
    """Testa que o callback de progresso não derruba a coleta com um blip de rede
    no Supabase, mas ainda honra o cancelamento quando a checagem tem sucesso."""

    @patch("worker_coleta.coletor_ldi.coletar")
    @patch("worker_coleta.extrator_ldi.montar_sessao")
    @patch("worker_coleta._status_pedido")
    @patch("worker_coleta._ler_cookie")
    @patch("worker_coleta._patch_pedido")
    def test_blip_de_rede_nao_propaga(
        self, mock_patch, mock_ler_cookie, mock_status, mock_sessao, mock_coletar
    ):
        """_patch_pedido falhando (blip de rede) no callback de progresso não deve
        derrubar a coleta — coletar() deve rodar até o fim normalmente."""
        mock_ler_cookie.return_value = _cookie_valido()
        mock_sessao.return_value = MagicMock()

        # primeira chamada (status="rodando") ok; demais chamadas do callback falham
        chamadas = {"n": 0}

        def patch_lado(rest, key, pid, campos):
            chamadas["n"] += 1
            if "progresso" in campos:
                raise Exception("conexão caiu")

        mock_patch.side_effect = patch_lado

        def coletar_chama_progresso(cfg, sessao, termo, banco, ids=None, progresso=None):
            # simula o coletor chamando o callback de progresso — não deve levantar
            progresso(1, 10)
            return 999

        mock_coletar.side_effect = coletar_chama_progresso

        row = {"id": 42, "tipo": "termo", "alvo": "PRF", "rotulo": None}
        cfg = {"vertical": "concursos"}
        rest, key = "http://mock", "mock_key"

        status = worker_coleta.processar_pedido(rest, key, row, cfg)

        # o blip de rede no callback não deve ter feito a coleta virar 'erro';
        # coletar() rodou até o fim e o pedido concluiu normalmente.
        self.assertEqual(status, "concluida")
        # _status_pedido não deve ter sido chamado, pois _patch_pedido já falhou antes
        mock_status.assert_not_called()

    @patch("worker_coleta.coletor_ldi.coletar")
    @patch("worker_coleta.extrator_ldi.montar_sessao")
    @patch("worker_coleta._status_pedido")
    @patch("worker_coleta._ler_cookie")
    @patch("worker_coleta._patch_pedido")
    def test_cancelando_levanta_coleta_cancelada(
        self, mock_patch, mock_ler_cookie, mock_status, mock_sessao, mock_coletar
    ):
        """Quando _status_pedido retorna 'cancelando' (sem blip de rede), o callback
        de progresso deve levantar ColetaCancelada — e o pedido vira 'cancelada'."""
        mock_ler_cookie.return_value = _cookie_valido()
        mock_sessao.return_value = MagicMock()
        mock_status.return_value = "cancelando"

        def coletar_chama_progresso(cfg, sessao, termo, banco, ids=None, progresso=None):
            progresso(1, 10)  # deve levantar ColetaCancelada
            return 999  # não deve chegar aqui

        mock_coletar.side_effect = coletar_chama_progresso

        row = {"id": 43, "tipo": "termo", "alvo": "PRF", "rotulo": None}
        cfg = {"vertical": "concursos"}
        rest, key = "http://mock", "mock_key"

        status = worker_coleta.processar_pedido(rest, key, row, cfg)

        self.assertEqual(status, "cancelada")


if __name__ == "__main__":
    unittest.main()
