#!/bin/bash
# Instala o motor de volumetria do NeuroLaudo (uso em pesquisa, não validado para diagnóstico).
#
# Põe tudo em uma pasta só, sem mexer no resto do computador e sem precisar de Xcode:
#   - um Python próprio (3.11) com TensorFlow 2.13.1 e PyTorch 2.0.1;
#   - os programas mri_synthseg e mri_synthstrip do FreeSurfer 8.2.0 e os modelos
#     treinados deles, baixados dos endereços oficiais do FreeSurfer e conferidos
#     por soma SHA-256 (não é a instalação completa do FreeSurfer, de 20 GB);
#   - o motor do NeuroLaudo.
# Ocupa cerca de 2,5 GB. Para remover, apague a pasta mostrada no fim.
#
# Uso:  bash <(curl -fsSL https://raw.githubusercontent.com/mateusbarbqueiroz-max/neurolaudo/main/mac/instalar-volumetria.sh)
#
# Variáveis opcionais: NEUROLAUDO_MOTOR (pasta de destino), NEUROLAUDO_FONTE (pasta
# local com o motor, em vez de baixar do GitHub), NEUROLAUDO_SURFA (arquivo .whl da
# biblioteca surfa, em vez de baixar o que o projeto publica).
set -euo pipefail

REPO="mateusbarbqueiroz-max/neurolaudo"
FS_RAW="https://raw.githubusercontent.com/freesurfer/freesurfer/v8.2.0"
ANNEX="https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/repo/annex.git/annex/objects"
RODAS="https://github.com/$REPO/releases/download/motor"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)
    UV_ASSET="uv-aarch64-apple-darwin.tar.gz"
    PADRAO="$HOME/Library/Application Support/NeuroLaudo/motor" ;;
  Linux-x86_64)
    UV_ASSET="uv-x86_64-unknown-linux-gnu.tar.gz"
    PADRAO="$HOME/.local/share/neurolaudo/motor" ;;
  *)
    echo "Este instalador é para Mac com Apple Silicon (ou Linux de 64 bits, para teste). Aqui: $(uname -s) $(uname -m)." >&2
    exit 1 ;;
esac
MOTOR="${NEUROLAUDO_MOTOR:-$PADRAO}"
FS="$MOTOR/freesurfer"
PY="$MOTOR/venv/bin/python"
export UV_CACHE_DIR="$MOTOR/cache"
export UV_PYTHON_INSTALL_DIR="$MOTOR/python"

soma() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# baixar ENDEREÇO DESTINO SOMA: baixa se ainda não estiver lá com a soma certa, e confere.
baixar() {
  if [ -f "$2" ] && [ "$(soma "$2")" = "$3" ]; then return 0; fi
  curl -fL --retry 3 --retry-delay 5 -sS -o "$2.parcial" "$1"
  if [ "$(soma "$2.parcial")" != "$3" ]; then
    rm -f "$2.parcial"
    echo "O arquivo baixado de $1 não confere com a soma esperada. Nada foi instalado dele." >&2
    exit 1
  fi
  mv "$2.parcial" "$2"
}

mkdir -p "$MOTOR/bin" "$FS/bin" "$FS/models"
echo "Instalando o motor de volumetria em: $MOTOR"

echo "1/5  Python próprio do motor"
if [ ! -x "$MOTOR/bin/uv" ]; then
  rm -rf "$MOTOR/uv-tmp" && mkdir -p "$MOTOR/uv-tmp"
  curl -fL --retry 3 -sS "https://github.com/astral-sh/uv/releases/latest/download/$UV_ASSET" | tar -xz -C "$MOTOR/uv-tmp"
  mv "$MOTOR"/uv-tmp/*/uv "$MOTOR/bin/uv"
  rm -rf "$MOTOR/uv-tmp"
fi
UV="$MOTOR/bin/uv"
if [ ! -x "$PY" ]; then
  "$UV" venv --quiet --python-preference only-managed --python 3.11 "$MOTOR/venv"
fi

echo "2/5  Bibliotecas de cálculo (cerca de 400 MB para baixar)"
PACOTES="numpy==1.24.3 tensorflow==2.13.1 scipy==1.10.1 h5py==3.9.0 nibabel==5.2.1 matplotlib==3.7.5 pydicom>=2.4,<4"
if [ "$(uname -s)" = "Linux" ]; then
  # Em Linux o PyTorch sem placa de vídeo vem do índice do próprio PyTorch.
  # shellcheck disable=SC2086
  "$UV" pip install --quiet --python "$PY" --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match $PACOTES "torch==2.0.1+cpu"
else
  # shellcheck disable=SC2086
  "$UV" pip install --quiet --python "$PY" $PACOTES "torch==2.0.1"
fi

echo "3/5  Biblioteca surfa, do FreeSurfer"
if [ -n "${NEUROLAUDO_SURFA:-}" ]; then
  "$UV" pip install --quiet --python "$PY" "$NEUROLAUDO_SURFA"
elif [ "$(uname -s)" = "Darwin" ]; then
  # A surfa só existe em código-fonte e exigiria um compilador. O projeto publica uma já compilada.
  mkdir -p "$MOTOR/rodas"
  RODA="$(curl -fL --retry 3 -sS "$RODAS/surfa-macos-arm64.txt" | tr -d '[:space:]')"
  curl -fL --retry 3 -sS -o "$MOTOR/rodas/$RODA" "$RODAS/$RODA"
  "$UV" pip install --quiet --python "$PY" "$MOTOR/rodas/$RODA"
else
  "$UV" pip install --quiet --python "$PY" "surfa==0.6.3"
fi

echo "4/5  Programas e modelos de segmentação do FreeSurfer 8.2.0 (cerca de 135 MB)"
baixar "$FS_RAW/mri_synthseg/mri_synthseg" "$FS/bin/mri_synthseg" f3c182cd100721e8ae4ae4e0661b6ac3c45e80453f716d668d53ca0fe189279b
baixar "$FS_RAW/mri_synthstrip/mri_synthstrip" "$FS/bin/mri_synthstrip" bbc2ff8f8779862039401b05d5cd6039fb4f3583e0032a793ac9adb3f4521590
while read -r SOMA NOME; do
  baixar "$FS_RAW/mri_synthseg/$NOME" "$FS/models/$NOME" "$SOMA"
done <<'LISTA'
bdad22b13216ce0addbaa0baf0ba8b8451f87b11f2cba01509cd75d9d1d235aa synthseg_denoiser_labels_2.0.npy
85aeb75d0d10d7c5968269a9b1bc0a1b87739a3de6d3fcaa8b294ea4dd2af46a synthseg_parcellation_labels.npy
ea78f9b7e4899608e1ac2318ebf649a1d5efcd806a6342e52ae5b5178926903d synthseg_parcellation_names.npy
a0c62354beac265ef31e0c97056f16d6b2058cddc2dfdc1d602d515248967bd4 synthseg_qc_labels_2.0.npy
08d123a2b0ad6b630cd36d915ae71c486844f4124d1d82bb7d3dd983e4eaf852 synthseg_qc_names_2.0.npy
5ef25ec33fe917ac99f30b8f2185b2d77121136ee411b9c4970c0b59be615ed8 synthseg_segmentation_labels_2.0.npy
234eb6d514e10d6ebd748a8b30a1d12d9426fd874c607e37852406fae8f290fc synthseg_segmentation_names_2.0.npy
650b4b96834485c1e6d7421de4af74da80d861e6b2a39ef1164389bde3a5e14a synthseg_topological_classes_2.0.npy
LISTA
# Modelos treinados: no repositório do FreeSurfer são ponteiros para estes arquivos (a soma faz parte do nome).
while read -r PASTA SOMA TAMANHO SUFIXO NOME; do
  CHAVE="SHA256E-s$TAMANHO--$SOMA$SUFIXO"
  baixar "$ANNEX/$PASTA/$CHAVE/$CHAVE" "$FS/models/$NOME" "$SOMA"
done <<'LISTA'
bee/241 f190bfd742f450ef3ca2c9df9ed4d2e0232b3a74471da5e51b7770bacdf80c3e 53079152 .0.h5 synthseg_2.0.h5
3ac/fe4 fb92e37daa0842bdd8a03bc06a3b36b0d38810e31c714659cedd09119c0abfb7 49878004 .0.h5 synthseg_qc_2.0.h5
fdd/51c 37417f802196186441aae3e7f385d94f8a98c64a88acaeaa2723af995c653e33 30851709 .1.pt synthstrip.1.pt
LISTA

echo "5/5  Motor do NeuroLaudo"
if [ -n "${NEUROLAUDO_FONTE:-}" ]; then
  "$UV" pip install --quiet --python "$PY" "$NEUROLAUDO_FONTE"
else
  "$UV" pip install --quiet --python "$PY" --reinstall-package neurolaudo \
    "neurolaudo @ https://github.com/$REPO/archive/refs/heads/main.zip#subdirectory=engine"
fi
rm -rf "$UV_CACHE_DIR"

echo "Conferindo a instalação"
NEUROLAUDO_MOTOR="$MOTOR" TF_CPP_MIN_LOG_LEVEL=3 "$PY" - <<'CONFERE'
import tensorflow, torch, surfa, nibabel, numpy
print(f"  TensorFlow {tensorflow.__version__}, PyTorch {torch.__version__}, surfa {surfa.__version__}, numpy {numpy.__version__}")
CONFERE
NEUROLAUDO_MOTOR="$MOTOR" "$PY" -m neurolaudo.volumetry.cli verificar

echo
echo "Pronto. O motor de volumetria está em:"
echo "  $MOTOR"
echo "Uso em pesquisa. Não validado para diagnóstico."
