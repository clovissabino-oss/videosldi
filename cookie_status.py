# -*- coding: utf-8 -*-
"""Validade do cookie __Secure-SID do LDI (compartilhado: visualizador e worker)."""
import base64
import json
import re
import time
from datetime import datetime, timezone


def decodifica_sid(cookie_bruto):
    """Extrai {email, expira_ts} do token __Secure-SID; {} se não achar/decodificar."""
    m = re.search(r"__Secure-SID=([^;\s]+)", cookie_bruto or "")
    if not m:
        return {}
    try:
        payload = m.group(1).split(".")[1]
        payload += "=" * (-len(payload) % 4)
        j = json.loads(base64.urlsafe_b64decode(payload))
        return {"email": j.get("email", ""), "expira_ts": j.get("exp")}
    except Exception:
        return {}


def resumo_validade(cookie_bruto):
    """Resumo sem rede: {email, expira_em(iso|None), dias_restantes(float|None), valido}.
    valido = há exp no futuro (não faz probe HTTP; o worker pode complementar com probe)."""
    sid = decodifica_sid(cookie_bruto)
    exp = sid.get("expira_ts")
    if not exp:
        return {"email": "", "expira_em": None, "dias_restantes": None, "valido": False}
    return {
        "email": sid.get("email", ""),
        "expira_em": datetime.fromtimestamp(exp, timezone.utc).isoformat(),
        "dias_restantes": round((exp - time.time()) / 86400, 1),
        "valido": exp > time.time(),
    }
