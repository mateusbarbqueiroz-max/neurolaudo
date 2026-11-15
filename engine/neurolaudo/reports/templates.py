"""Modelos de laudo estruturado de neurorradiologia.

Cada modelo tem título, técnica e seções com o texto "normal" padrão. O médico
edita apenas o que é alterado. Novos modelos podem ser adicionados aqui (e no
futuro carregados de arquivos do usuário).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    technique: str
    findings: list[str]
    impression: str


TEMPLATES: list[Template] = [
    Template(
        key="tc_cranio",
        title="TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO",
        technique="Exame realizado em aparelho multidetector, com aquisição volumétrica "
                  "e reconstruções multiplanares, sem a administração de contraste iodado.",
        findings=[
            "Parênquima encefálico com coeficientes de atenuação preservados.",
            "Diferenciação entre as substâncias branca e cinzenta preservada.",
            "Ausência de coleções intra ou extra-axiais.",
            "Sistema ventricular de dimensões e morfologia habituais, centrado.",
            "Sulcos corticais e fissuras encefálicas de aspecto habitual para a faixa etária.",
            "Cisternas da base livres.",
            "Estruturas da linha média centradas.",
            "Calota craniana íntegra.",
        ],
        impression="Exame tomográfico do crânio dentro dos limites da normalidade.",
    ),
    Template(
        key="tc_avc",
        title="TOMOGRAFIA COMPUTADORIZADA DO CRÂNIO — PROTOCOLO AVC",
        technique="Exame realizado em caráter de urgência, em aparelho multidetector, "
                  "sem contraste iodado, com reconstruções multiplanares.",
        findings=[
            "Ausência de sinais de hemorragia intracraniana.",
            "Não há sinais tomográficos de isquemia aguda estabelecida.",
            "ASPECTS: {aspects}.",
            "Sem sinal da artéria hiperdensa.",
            "Sistema ventricular de dimensões normais, centrado.",
            "Ausência de desvio das estruturas da linha média.",
        ],
        impression="Ausência de hemorragia intracraniana. ASPECTS {aspects}.",
    ),
    Template(
        key="angio_tc",
        title="ANGIOTOMOGRAFIA ARTERIAL INTRACRANIANA E CERVICAL",
        technique="Aquisição volumétrica após injeção endovenosa de contraste iodado, "
                  "com reconstruções MPR, MIP e volumétricas.",
        findings=[
            "Artérias carótidas comuns, bifurcações e carótidas internas cervicais pérvias, "
            "sem estenoses hemodinamicamente significativas.",
            "Artérias vertebrais pérvias, com calibre simétrico.",
            "Segmentos intracranianos das carótidas internas pérvios.",
            "Artérias cerebrais anteriores, médias e posteriores pérvias, sem falhas de enchimento.",
            "Artéria basilar pérvia.",
            "Ausência de dilatações aneurismáticas com as limitações do método.",
            "Polígono de Willis completo.",
        ],
        impression="Angiotomografia arterial intracraniana e cervical sem alterações significativas.",
    ),
    Template(
        key="rm_encefalo",
        title="RESSONÂNCIA MAGNÉTICA DO ENCÉFALO",
        technique="Exame realizado em aparelho de alto campo, com sequências multiplanares "
                  "ponderadas em T1, T2, FLAIR, difusão, SWI e T1 pós-contraste (gadolínio).",
        findings=[
            "Parênquima encefálico com morfologia e intensidade de sinal preservadas.",
            "Ausência de restrição à difusão das moléculas de água.",
            "Ausência de focos de deposição de hemossiderina nas sequências de susceptibilidade magnética.",
            "Ausência de realce anômalo após a administração do meio de contraste.",
            "Sistema ventricular de dimensões normais, centrado.",
            "Espaços liquóricos da convexidade de aspecto habitual.",
            "Estruturas da fossa posterior sem alterações.",
            "Sela túrcica e região selar de aspecto habitual.",
            "Flow voids vasculares preservados.",
        ],
        impression="Ressonância magnética do encéfalo dentro dos limites da normalidade.",
    ),
    Template(
        key="rm_hipofise",
        title="RESSONÂNCIA MAGNÉTICA DA SELA TÚRCICA (HIPÓFISE)",
        technique="Sequências finas coronais e sagitais T1 e T2, com estudo dinâmico "
                  "e tardio após a administração de gadolínio.",
        findings=[
            "Hipófise de dimensões normais, com altura de {altura} mm.",
            "Intensidade de sinal e padrão de realce homogêneos, inclusive no estudo dinâmico.",
            "Haste hipofisária centrada.",
            "Neuro-hipófise com hipersinal T1 habitual.",
            "Seios cavernosos simétricos.",
            "Quiasma óptico sem alterações.",
        ],
        impression="Hipófise sem alterações.",
    ),
]

TEMPLATES_BY_KEY = {t.key: t for t in TEMPLATES}


def render_text(t: Template, values: dict[str, str] | None = None) -> str:
    """Texto editável do laudo. Placeholders {campo} não preenchidos ficam como '___'."""
    values = values or {}

    class _Default(dict):
        def __missing__(self, key):
            return "___"

    v = _Default(values)
    lines = [t.title, "", "TÉCNICA:", t.technique.format_map(v), "", "ANÁLISE:"]
    lines += [f"- {f.format_map(v)}" for f in t.findings]
    lines += ["", "IMPRESSÃO:", t.impression.format_map(v)]
    return "\n".join(lines)
