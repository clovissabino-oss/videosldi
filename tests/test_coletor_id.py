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
