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
