"""Comparação da volumetria com o exame anterior do mesmo paciente. Uso em pesquisa, não validado para diagnóstico.

O histórico fica só no Mac do usuário, na pasta que o complemento passa ao motor
(~/Library/Application Support/NeuroLaudo/historico). Cada exame medido vira um arquivo pequeno com os volumes,
a data do exame, a idade, o sexo e os parâmetros da aquisição. Nome, identificador do paciente e UIDs não são
gravados: o identificador e o UID do exame entram embaralhados (HMAC-SHA-256 com uma chave aleatória deste Mac,
guardada na mesma pasta), só para reconhecer de novo o mesmo paciente e o mesmo exame. Apagar a pasta apaga o
histórico.

A variação entre dois exames é comparada com a que só a repetição do exame produz, medida em voluntários
públicos escaneados várias vezes (data/repeticao.json, feito por scripts/retest_summary.py): no mesmo aparelho,
quando a aquisição dos dois exames é igual, e entre aparelhos diferentes, quando não é.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from neurolaudo.volumetry.norms import Assessment, Norms

RECORD_VERSION = 1
# O que o motor mede. Muda quando muda o que sai dele (segmentador, recorte): exames medidos de jeitos
# diferentes não se comparam sem aviso.
METHOD = "SynthSeg 2.0 rápido, recorte em dois passos"
KEY_FILE = "chave"
AGE_TOLERANCE_YEARS = 0.25    # a diferença de idade entre os exames tem de fechar com a das datas
MIN_YEARS_FOR_RATE = 0.5      # abaixo disso a taxa por ano só aumentaria o ruído
DEFAULT_REPEATABILITY = Path(__file__).parent / "data" / "repeticao.json"
SCENARIO_TEXT = {"mesmo_aparelho": "mesmo aparelho", "aparelhos_diferentes": "aparelhos diferentes"}


def br(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def signed(value: float, decimals: int = 1) -> str:
    text = br(abs(value), decimals)
    return text if text.strip("0,") == "" else ("+" if value > 0 else "-") + text


def date_text(d: str) -> str:
    return f"{d[6:8]}/{d[4:6]}/{d[0:4]}" if len(d) == 8 and d.isdigit() else d


def _date(d: str) -> datetime | None:
    try:
        return datetime.strptime(d, "%Y%m%d")
    except (TypeError, ValueError):
        return None


def years_between(first: str, second: str) -> float:
    a, b = _date(first), _date(second)
    return (b - a).days / 365.2425 if a and b else 0.0


def interval_text(first: str, second: str) -> str:
    a, b = _date(first), _date(second)
    if not a or not b:
        return "intervalo desconhecido"
    days = (b - a).days
    if days < 45:
        return f"{days} dia{'s' if days != 1 else ''}"
    months = round(days / 30.4369)
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} ano{'s' if years > 1 else ''}")
    if months:
        parts.append(f"{months} {'mês' if months == 1 else 'meses'}")
    return " e ".join(parts)


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


# MARK: histórico

def load_secret(folder: Path) -> bytes:
    """A chave aleatória deste Mac que embaralha identificadores. Criada na primeira vez, só o usuário lê."""
    folder.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(folder, 0o700)
    except OSError:
        pass
    path = folder / KEY_FILE
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        data = path.read_bytes()
        if len(data) < 32:
            raise OSError(f"a chave do histórico em {path} está incompleta")
        return data
    data = secrets.token_bytes(32)
    with os.fdopen(descriptor, "wb") as fh:
        fh.write(data)
    return data


def scramble(secret: bytes, kind: str, text: str) -> str:
    return hmac.new(secret, f"{kind}:{text.strip()}".encode("utf-8"), hashlib.sha256).hexdigest()


def make_record(assessment: Assessment, tracking: Mapping, voxels: Sequence[int], voxel_mm: Sequence[float],
                secret: bytes) -> dict | None:
    """O que fica guardado deste exame, ou None se faltar o paciente, o exame ou a data."""
    patient = str(tracking.get("id") or "").strip()
    exam = str(tracking.get("exame") or "").strip()
    when = str(tracking.get("data") or "").strip()
    if not patient or not exam or _date(when) is None:
        return None
    acquisition = tracking.get("aquisicao") or {}
    return {
        "versao": RECORD_VERSION, "metodo": METHOD,
        "paciente": scramble(secret, "paciente", patient), "exame": scramble(secret, "exame", exam),
        "data": when, "idade": assessment.age, "sexo": assessment.model_key,
        "serie": str(tracking.get("serie") or ""),
        "aquisicao": {"voxels": [int(v) for v in voxels], "voxel_mm": [round(float(z), 3) for z in voxel_mm],
                      "tr_ms": _number(acquisition.get("tr")), "te_ms": _number(acquisition.get("te"))},
        "icv_mm3": round(assessment.icv_mm3, 1),
        "volumes_mm3": {r.structure.id: round(r.volume_mm3, 1) for r in assessment.results},
        "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _file(folder: Path, record: Mapping) -> Path:
    return folder / f"{record['paciente'][:24]}-{record['exame'][:24]}.json"


def save(folder: Path, record: Mapping) -> Path:
    """Grava o exame no histórico. Medir de novo o mesmo exame troca o registro antigo."""
    path = _file(folder, record)
    temporary = path.with_suffix(".novo")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    os.replace(temporary, path)
    return path


def _same_person(a: Mapping, b: Mapping) -> bool:
    if a.get("sexo") != b.get("sexo") and "all" not in (a.get("sexo"), b.get("sexo")):
        return False
    if a.get("idade") is not None and b.get("idade") is not None:
        expected = years_between(a["data"], b["data"])
        if abs((b["idade"] - a["idade"]) - expected) > AGE_TOLERANCE_YEARS:
            return False
    return True


def earlier_exams(folder: Path, record: Mapping) -> tuple[list[dict], list[str]]:
    """Exames anteriores do mesmo paciente, do mais antigo ao mais recente, e avisos sobre os deixados de fora."""
    found, mismatched = [], 0
    for path in sorted(folder.glob(f"{record['paciente'][:24]}-*.json")):
        try:
            other = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if other.get("paciente") != record["paciente"] or other.get("exame") == record["exame"]:
            continue
        if not str(other.get("data", "")) < record["data"] or not isinstance(other.get("volumes_mm3"), dict):
            continue
        if not _same_person(other, record):
            mismatched += 1
            continue
        found.append(other)
    found.sort(key=lambda r: r["data"])
    notes = []
    if mismatched:
        notes.append(f"{mismatched} exame(s) anterior(es) com o mesmo identificador, mas com idade ou sexo que não "
                     "fecham com este, ficaram fora da comparação.")
    return found, notes


# MARK: comparação

def load_repeatability(path: str | Path | None = None) -> dict | None:
    p = Path(path or DEFAULT_REPEATABILITY)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _voxel_text(sizes: Sequence[float]) -> str:
    return " × ".join(br(float(z), 2) for z in sizes)


def acquisition_differences(a: Mapping, b: Mapping) -> list[str]:
    """O que muda na aquisição entre dois exames. TR e TE desconhecidos contam como diferença: sem eles não dá
    para dizer que é o mesmo protocolo."""
    first, second = a.get("aquisicao") or {}, b.get("aquisicao") or {}
    out = []
    va, vb = sorted(first.get("voxel_mm") or []), sorted(second.get("voxel_mm") or [])
    if len(va) != 3 or len(vb) != 3 or any(abs(x - y) > 0.05 for x, y in zip(va, vb)):
        out.append(f"voxel {_voxel_text(first.get('voxel_mm') or [])} mm → {_voxel_text(second.get('voxel_mm') or [])} mm")
    for key, name in (("tr_ms", "TR"), ("te_ms", "TE")):
        x, y = first.get(key), second.get(key)
        if not x or not y:
            out.append(f"{name} desconhecido")
        elif abs(x - y) > 0.02 * max(x, y):
            out.append(f"{name} {br(x, 1)} → {br(y, 1)} ms")
    return out


def adjusted_mm3(norms: Norms, record: Mapping, structure_id: str, model_key: str) -> float:
    """Volume ajustado ao volume intracraniano do próprio exame, como nos percentis."""
    structure = norms.structure(structure_id)
    volume = float(record["volumes_mm3"][structure_id])
    slope = structure.models[model_key].icv_slope
    return math.exp(math.log(volume) - slope * math.log(float(record["icv_mm3"]) / norms.reference_icv_mm3))


def compare(norms: Norms, prior: Mapping, current: Mapping, repeatability: Mapping | None) -> dict:
    """Variação de cada estrutura entre o exame anterior e o atual, com o limite da repetição."""
    differences = acquisition_differences(prior, current)
    scenario = "aparelhos_diferentes" if differences else "mesmo_aparelho"
    # Só faltam TR ou TE: não dá para dizer que é diferente, só que não dá para confirmar que é igual.
    acquisition = "igual" if not differences else (
        "não confirmada" if all(d.endswith("desconhecido") for d in differences) else "diferente")
    measure = (repeatability or {}).get("medida", "ajustado")
    limits = ((repeatability or {}).get("variantes") or {}).get(measure) or {}
    years = years_between(prior["data"], current["data"])
    key = current.get("sexo") if current.get("sexo") in ("female", "male") else prior.get("sexo") or "all"
    rows = []
    for structure in norms.structures:
        v0, v1 = prior["volumes_mm3"].get(structure.id), current["volumes_mm3"].get(structure.id)
        if not v0 or not v1:
            continue
        if measure == "bruto":
            ratio = v1 / v0
        else:
            ratio = adjusted_mm3(norms, current, structure.id, key) / adjusted_mm3(norms, prior, structure.id, key)
        limit = ((limits.get(structure.id) or {}).get(scenario) or {}).get("limite_pct")
        mark = ""
        if limit is not None and abs(100 * math.log(ratio)) > limit:
            mark = "redução" if ratio < 1 else "aumento"
        rows.append({"id": structure.id, "nome": structure.title,
                     "anterior_ml": round(v0 / 1000, 2), "atual_ml": round(v1 / 1000, 2),
                     "variacao_pct": round(100 * (ratio - 1), 1),
                     "por_ano_pct": round(100 * (ratio ** (1 / years) - 1), 1) if years >= MIN_YEARS_FOR_RATE else None,
                     "limite_pct": None if limit is None else round(limit, 1), "marca": mark})
    notes = []
    if prior.get("metodo") != current.get("metodo"):
        notes.append(f"O exame anterior foi medido com outra versão do motor ({prior.get('metodo') or 'desconhecida'}); "
                     "parte da diferença pode vir disso.")
    if acquisition == "diferente":
        notes.append("Aquisição diferente da do exame anterior (" + "; ".join(differences) + "): usada a variação "
                     "esperada entre aparelhos diferentes, que é maior.")
    elif acquisition == "não confirmada":
        notes.append("Sem TR ou TE em um dos exames, não dá para confirmar que a aquisição é a mesma: usada a variação "
                     "esperada entre aparelhos diferentes, que é maior.")
    if not limits:
        notes.append("A variação esperada só pela repetição do exame não está disponível nesta instalação: "
                     "a tabela não marca nenhuma estrutura.")
    if years < MIN_YEARS_FOR_RATE:
        notes.append("Intervalo menor que 6 meses: sem taxa por ano.")
    comparison = {"anterior": {"data": prior["data"], "idade": prior.get("idade"), "serie": prior.get("serie", "")},
                  "intervalo_anos": round(years, 2), "intervalo": interval_text(prior["data"], current["data"]),
                  "cenario": scenario, "aquisicao": acquisition, "diferencas_aquisicao": differences, "medida": measure,
                  "estruturas": rows, "avisos": notes}
    comparison["frase"] = sentence(comparison)
    return comparison


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " e " + parts[-1]


def sentence(comparison: Mapping) -> str:
    """Uma frase para o laudo."""
    detail = comparison["intervalo"] + ("; aquisição diferente" if comparison.get("aquisicao") == "diferente" else "")
    head = f"Comparação com o exame de {date_text(comparison['anterior']['data'])} ({detail})"
    rows = comparison["estruturas"]
    if not rows:
        return head + ": nenhuma estrutura para comparar."
    if all(r["limite_pct"] is None for r in rows):
        picked = [r for r in rows if r["id"] in ("hippocampus_left", "hippocampus_right", "lateral_ventricles")] or rows
        return head + ": " + _join([f"{r['nome'].lower()} {signed(r['variacao_pct'])} %" for r in picked]) + "."
    flagged = [r for r in rows if r["marca"]]
    if not flagged:
        return head + ": nenhuma estrutura variou além do esperado só pela repetição do exame."
    return head + ": variação além do esperado só pela repetição do exame em " + _join(
        [f"{r['nome'].lower()} ({signed(r['variacao_pct'])} %; esperado até ±{br(r['limite_pct'])} %)" for r in flagged]) + "."
