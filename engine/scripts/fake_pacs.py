"""PACS de teste: responde a buscas (C-FIND) e envia exames (C-MOVE), para simular o botão do PACS.

Uso: python fake_pacs.py PASTA --ae PACSFALSO --porta 11112 --destino ISIXTESTE=127.0.0.1:11113

Serve os arquivos DICOM da PASTA (exames de teste, nunca de paciente). Diferente do `qrscp` do
pynetdicom, informa quantas imagens cada exame e cada série têm (NumberOfStudyRelatedInstances e
NumberOfSeriesRelatedInstances): é por esse número que o IsiX decide, com
`retrieveOnlyIfNeeded=yes`, se o exame já está completo no Mac.

Cada pedido recebido vira uma linha na saída ("C-FIND STUDY ...", "C-MOVE STUDY ..."), para o teste
contar quantas vezes o exame foi buscado.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from collections import defaultdict
from pathlib import Path

from pydicom import dcmread
from pydicom.dataset import Dataset
from pynetdicom import AE, StoragePresentationContexts, evt
from pynetdicom.sop_class import (PatientRootQueryRetrieveInformationModelFind,
                                  PatientRootQueryRetrieveInformationModelMove,
                                  StudyRootQueryRetrieveInformationModelFind,
                                  StudyRootQueryRetrieveInformationModelMove, Verification)

LEVEL_KEYS = {"PATIENT": "PatientID", "STUDY": "StudyInstanceUID", "SERIES": "SeriesInstanceUID",
              "IMAGE": "SOPInstanceUID"}
IGNORED = {"QueryRetrieveLevel", "SpecificCharacterSet", "RetrieveAETitle", "InstanceAvailability"}


def say(text: str) -> None:
    print(text, flush=True)


class Archive:
    """Os arquivos da pasta, com os valores de cabeçalho usados nas buscas."""

    def __init__(self, folder: Path):
        self.paths: dict[str, Path] = {}
        self.headers: dict[str, Dataset] = {}
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            try:
                header = dcmread(str(path), stop_before_pixels=True)
            except Exception:
                continue
            if "SOPInstanceUID" not in header:
                continue
            self.paths[header.SOPInstanceUID] = path
            self.headers[header.SOPInstanceUID] = header
        by_study, by_series = defaultdict(set), defaultdict(set)
        for uid, header in self.headers.items():
            by_study[header.StudyInstanceUID].add(uid)
            by_series[header.SeriesInstanceUID].add(uid)
        self.by_study, self.by_series = by_study, by_series

    def value(self, header: Dataset, keyword: str):
        """Valor de um atributo para a resposta, incluindo os que se calculam."""
        if keyword == "NumberOfStudyRelatedInstances":
            return len(self.by_study[header.StudyInstanceUID])
        if keyword == "NumberOfStudyRelatedSeries":
            return len({self.headers[u].SeriesInstanceUID for u in self.by_study[header.StudyInstanceUID]})
        if keyword == "NumberOfSeriesRelatedInstances":
            return len(self.by_series[header.SeriesInstanceUID])
        if keyword == "ModalitiesInStudy":
            return sorted({self.headers[u].Modality for u in self.by_study[header.StudyInstanceUID]})
        return header.get(keyword, None)

    def matches(self, identifier: Dataset, level: str) -> list[Dataset]:
        """Um cabeçalho representante por exame, série ou imagem que case com a busca."""
        wanted = [(elem.keyword, elem.value) for elem in identifier
                  if elem.keyword and elem.keyword not in IGNORED and elem.value not in (None, "", [])]
        seen, found = set(), []
        for header in self.headers.values():
            key = str(header.get(LEVEL_KEYS[level], ""))
            if key in seen:
                continue
            ok = True
            for keyword, value in wanted:
                have = self.value(header, keyword)
                if have is None:
                    ok = False
                    break
                values = [str(v) for v in value] if isinstance(value, (list, tuple)) or getattr(value, "VM", 1) > 1 \
                    else [str(value)]
                text = str(have)
                if not any(fnmatch.fnmatchcase(text, v.replace("?", "?")) if ("*" in v or "?" in v) else text == v
                           for v in values):
                    ok = False
                    break
            if ok:
                seen.add(key)
                found.append(header)
        return found

    def instances(self, identifier: Dataset, level: str) -> list[Path]:
        paths = []
        for header in self.matches(identifier, level):
            if level == "STUDY":
                uids = self.by_study[header.StudyInstanceUID]
            elif level == "SERIES":
                uids = self.by_series[header.SeriesInstanceUID]
            elif level == "PATIENT":
                uids = {u for u, h in self.headers.items() if h.get("PatientID") == header.get("PatientID")}
            else:
                uids = {header.SOPInstanceUID}
            paths += [self.paths[u] for u in sorted(uids)]
        return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pasta", type=Path)
    parser.add_argument("--ae", default="PACSFALSO")
    parser.add_argument("--porta", type=int, default=11112)
    parser.add_argument("--destino", action="append", default=[], help="AE=endereço:porta (pode repetir)")
    args = parser.parse_args(argv)

    archive = Archive(args.pasta)
    destinations = {}
    for item in args.destino:
        name, address = item.split("=", 1)
        host, port = address.rsplit(":", 1)
        destinations[name.strip()] = (host, int(port))
    say(f"PACS de teste {args.ae} na porta {args.porta}: {len(archive.by_study)} exame(s), {len(archive.paths)} imagem(ns); "
        f"destinos: {', '.join(destinations) or 'nenhum'}")

    def handle_find(event):
        identifier = event.identifier
        level = str(identifier.get("QueryRetrieveLevel", "STUDY"))
        found = archive.matches(identifier, level) if level in LEVEL_KEYS else []
        say(f"C-FIND {level} de {event.assoc.requestor.ae_title}: {len(found)} resposta(s)")
        for header in found:
            if event.is_cancelled:
                yield 0xFE00, None
                return
            answer = Dataset()
            answer.QueryRetrieveLevel = level
            for elem in identifier:
                if not elem.keyword or elem.keyword == "QueryRetrieveLevel":
                    continue
                value = archive.value(header, elem.keyword)
                setattr(answer, elem.keyword, "" if value is None else value)
            answer.RetrieveAETitle = args.ae
            yield 0xFF00, answer

    def handle_move(event):
        identifier = event.identifier
        level = str(identifier.get("QueryRetrieveLevel", "STUDY"))
        destination = event.move_destination.strip() if isinstance(event.move_destination, str) \
            else event.move_destination.decode().strip()
        paths = archive.instances(identifier, level) if level in LEVEL_KEYS else []
        say(f"C-MOVE {level} de {event.assoc.requestor.ae_title} para {destination}: {len(paths)} imagem(ns)")
        if destination not in destinations:
            say(f"destino desconhecido: {destination}")
            yield None, None
            return
        host, port = destinations[destination]
        yield host, port
        yield len(paths)
        for path in paths:
            if event.is_cancelled:
                yield 0xFE00, None
                return
            yield 0xFF00, dcmread(str(path))

    ae = AE(ae_title=args.ae)
    ae.supported_contexts = []
    for sop in (Verification, StudyRootQueryRetrieveInformationModelFind, StudyRootQueryRetrieveInformationModelMove,
                PatientRootQueryRetrieveInformationModelFind, PatientRootQueryRetrieveInformationModelMove):
        ae.add_supported_context(sop)
    ae.requested_contexts = StoragePresentationContexts[:120]
    handlers = [(evt.EVT_C_FIND, handle_find), (evt.EVT_C_MOVE, handle_move),
                (evt.EVT_C_ECHO, lambda event: (say(f"C-ECHO de {event.assoc.requestor.ae_title}"), 0x0000)[1])]
    ae.start_server(("0.0.0.0", args.porta), block=True, evt_handlers=handlers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
