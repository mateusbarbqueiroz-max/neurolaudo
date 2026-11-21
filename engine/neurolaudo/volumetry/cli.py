"""Linha de comando da volumetria.

    exame      volumetria completa de um volume T1 em NIfTI (segmenta, compara, grava relatório e mapa)
    relatorio  só o relatório, a partir da tabela de volumes que o `mri_synthseg --vol` grava
    verificar  diz se o motor de segmentação está instalado

    python -m neurolaudo.volumetry.cli exame --nifti t1.nii --idade 72 --sexo F --saida pasta
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys

from neurolaudo.volumetry.norms import assess, load_norms
from neurolaudo.volumetry.report import DISCLAIMER, ReportHeader, save_pdf, save_png
from neurolaudo.volumetry.tables import read_volumes_csv, result_json


def run_report(args: argparse.Namespace) -> int:
    volumes = read_volumes_csv(args.csv, args.linha)
    assessment = assess(load_norms(), volumes, age=args.idade, sex=args.sexo)
    header = ReportHeader(patient_name=args.nome or "", patient_id=args.id or "", sex=args.sexo or "",
                          exam_date=args.data or "", series=args.serie or "")
    os.makedirs(args.saida, exist_ok=True)
    save_pdf(os.path.join(args.saida, "relatorio.pdf"), assessment, header)
    save_png(os.path.join(args.saida, "relatorio.png"), assessment, header)
    with open(os.path.join(args.saida, "resultado.json"), "w", encoding="utf-8") as fh:
        json.dump(result_json(assessment), fh, ensure_ascii=False, indent=1)
    flagged = [r.structure.title for r in assessment.results if r.flag]
    print(f"Relatório gravado em {args.saida}. Fora da faixa de 5 a 95: {', '.join(flagged) if flagged else 'nenhuma estrutura'}.")
    print(DISCLAIMER)
    return 0


def _read_header_file(args: argparse.Namespace) -> dict:
    if getattr(args, "cabecalho", None):
        with open(args.cabecalho, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _header_and_subject(args: argparse.Namespace, data: dict) -> tuple[ReportHeader, float | None, str | None]:
    """Cabeçalho, idade e sexo: do arquivo --cabecalho, com as opções da linha de comando por cima."""
    def pick(option: str, key: str):
        value = getattr(args, option, None)
        return value if value not in (None, "") else data.get(key)
    age = pick("idade", "idade")
    sex = pick("sexo", "sexo")
    header = ReportHeader(patient_name=str(pick("nome", "nome") or ""), patient_id=str(pick("id", "id") or ""),
                          sex=str(sex or ""), exam_date=str(pick("data", "data") or ""), series=str(pick("serie", "serie") or ""))
    return header, (None if age is None else float(age)), (None if sex is None else str(sex))


def run_exam_command(args: argparse.Namespace) -> int:
    from neurolaudo.volumetry.pipeline import run_exam

    data = _read_header_file(args)
    header, age, sex = _header_and_subject(args, data)

    def progress(fraction: float, message: str) -> None:
        print(f"PROGRESSO {fraction:.2f} {message}", flush=True)
        if args.progresso:   # para o complemento do IsiX acompanhar sem ler a saída do programa
            temporary = args.progresso + ".novo"
            with open(temporary, "w", encoding="utf-8") as fh:
                fh.write(f"{fraction:.2f}\t{message}\n")
            os.replace(temporary, args.progresso)

    result = run_exam(args.nifti, args.saida, age=age, sex=sex, header=header, threads=args.nucleos, progress=progress,
                      series_notes=[str(n) for n in data.get("avisos", [])], quality=args.qualidade,
                      refine=not args.um_passo, history_dir=args.historico, tracking=data)
    flagged = [e["nome"] for e in result["estruturas"] if e["marca"]]
    print(f"Volumetria gravada em {args.saida}. Fora da faixa de 5 a 95: {', '.join(flagged) if flagged else 'nenhuma estrutura'}.")
    for warning in result["avisos"]:
        print(f"Aviso: {warning}")
    print(DISCLAIMER)
    return 0


def run_check_command(args: argparse.Namespace) -> int:
    from neurolaudo.volumetry.pipeline import find_tools

    tools = find_tools()
    print(f"Motor de segmentação encontrado{' em ' + tools.home if tools.home else ''}.")
    print("SynthSeg: " + " ".join(tools.synthseg))
    return 0


def _add_header_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--idade", type=float, help="idade em anos na data do exame")
    parser.add_argument("--sexo", help="F ou M")
    parser.add_argument("--nome", help="nome a mostrar no cabeçalho")
    parser.add_argument("--id", help="identificador a mostrar no cabeçalho")
    parser.add_argument("--data", help="data do exame, AAAAMMDD")
    parser.add_argument("--serie", help="descrição da série usada")


def _stop(signum, frame) -> None:
    raise SystemExit(128 + signum)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="neurolaudo-volumetria", description="Volumetria cerebral com percentis por idade e sexo.")
    commands = parser.add_subparsers(dest="comando", required=True)
    report = commands.add_parser("relatorio", help="gera o relatório a partir de um CSV de volumes do SynthSeg")
    report.add_argument("--csv", required=True, help="CSV gravado por mri_synthseg --vol")
    report.add_argument("--linha", help="linha de dados (0 = primeira) ou nome do sujeito; padrão: primeira")
    report.add_argument("--saida", required=True, help="pasta de saída")
    _add_header_options(report)
    report.set_defaults(run=run_report)

    exam = commands.add_parser("exame", help="volumetria completa de um volume T1 em NIfTI")
    exam.add_argument("--nifti", required=True, help="volume T1 (.nii ou .nii.gz)")
    exam.add_argument("--saida", required=True, help="pasta de saída")
    exam.add_argument("--cabecalho", help="arquivo JSON com nome, id, data, serie, idade e sexo (evita nomes na linha de comando)")
    exam.add_argument("--nucleos", type=int, help="núcleos do processador a usar (padrão: até 8)")
    exam.add_argument("--progresso", help="arquivo onde gravar o andamento (fração e mensagem)")
    exam.add_argument("--um-passo", action="store_true",
                      help="segmenta uma vez só, sem o segundo passo com o recorte das normas (mais rápido, menos fiel)")
    exam.add_argument("--qualidade", action="store_true",
                      help="pede também as notas automáticas de qualidade (exige bem mais memória)")
    exam.add_argument("--historico", help="pasta do histórico deste Mac: guarda o exame e compara com o anterior "
                                          "do mesmo paciente (usa id, exame e data do --cabecalho)")
    _add_header_options(exam)
    exam.set_defaults(run=run_exam_command)

    check = commands.add_parser("verificar", help="diz se o motor de segmentação está instalado")
    check.set_defaults(run=run_check_command)
    args = parser.parse_args(argv)
    # Cancelar no IsiX encerra este programa (SIGTERM). Sem isto o SynthSeg, que roda em outro processo,
    # continuaria sozinho por muitos minutos. Como exceção, o subprocess.run em andamento encerra o SynthSeg.
    signal.signal(signal.SIGTERM, _stop)
    try:
        return args.run(args)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
