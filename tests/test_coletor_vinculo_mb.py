import os, tempfile, unittest
import banco_conteudo
import coletor_ldi
import extrator_ldi


class _Resp:
    def __init__(self, status, data=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._data = data or []
    def json(self):
        return {"data": self._data}


class _Sessao:
    """Devolve itens por capitulo conforme o path chamado."""
    def __init__(self, por_cap, status=200):
        self.por_cap = por_cap
        self.status = status
    def get(self, url, timeout=60):
        if self.status != 200:
            return _Resp(self.status)
        ch = url.rstrip("/").split("/chapters/")[1].split("/")[0]
        return _Resp(200, self.por_cap.get(ch, []))


class TestCompletarVinculoMB(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "c.db")
        self.con = banco_conteudo.abrir(self.db)
        # árvore mínima: 1 curso, 2 capítulos, 3 itens
        for (cap, item) in [("capA", "i1"), ("capA", "i2"), ("capB", "i3")]:
            self.con.execute(
                "INSERT OR REPLACE INTO aulas(extracao_id, curso_id, capitulo_id, item_id, nome) "
                "VALUES(1,'cur1',?,?,?)", (cap, item, item))
        self.con.commit()
        self.cursos = [{"id": "cur1", "content_tree_cache": [
            {"chapter_id": "capA"}, {"chapter_id": "capB"}]}]

    def test_grava_vinculo_por_item(self):
        sess = _Sessao({
            "capA": [{"id": "i1", "has_base_material": True},
                     {"id": "i2", "has_base_material": False}],
            "capB": [{"id": "i3", "has_base_material": True}],
        })
        coletor_ldi._completar_vinculo_mb(sess, self.con, 1, self.cursos, 2)
        got = {r[0]: r[1] for r in self.con.execute(
            "SELECT item_id, vinculado_mb FROM aulas WHERE extracao_id=1")}
        self.assertEqual((got["i1"], got["i2"], got["i3"]), (1, 0, 1))

    def test_401_vira_cookie_vencido(self):
        sess = _Sessao({}, status=401)
        with self.assertRaises(coletor_ldi.CookieVencido):
            coletor_ldi._completar_vinculo_mb(sess, self.con, 1, self.cursos, 2)


if __name__ == "__main__":
    unittest.main()
