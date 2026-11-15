#!/bin/bash
# Instala (ou atualiza) o complemento NeuroLaudo no IsiX DICOM Viewer.
#
# Baixa a última compilação publicada no GitHub e a coloca na pasta de
# complementos do IsiX, só para o usuário atual. Não altera o IsiX nem o OsiriX.
#
# ATENÇÃO: ainda não foi executado em um Mac de verdade (escrito em Linux).
set -euo pipefail

REPOSITORIO="${NEUROLAUDO_REPOSITORIO:-mateusbarbqueiroz-max/neurolaudo}"
URL="https://github.com/$REPOSITORIO/releases/latest/download/NeuroLaudo.isixplugin.zip"
DESTINO="$HOME/Library/Application Support/IsiX/Plugins"
NOME="NeuroLaudo.isixplugin"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "Este instalador é para macOS." >&2
    exit 2
fi

if pgrep -f "IsiX DICOM Viewer.app/Contents/MacOS/" >/dev/null 2>&1; then
    echo "Feche o IsiX DICOM Viewer e rode este comando de novo." >&2
    exit 1
fi

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

echo "Baixando o NeuroLaudo..."
if ! curl -fsSL "$URL" -o "$TEMP/complemento.zip"; then
    echo "Não consegui baixar de $URL." >&2
    echo "Confira a internet. Se o repositório for privado, o download direto não funciona." >&2
    exit 1
fi

ditto -x -k "$TEMP/complemento.zip" "$TEMP/aberto"
if [[ ! -d "$TEMP/aberto/$NOME" ]]; then
    echo "O arquivo baixado não contém $NOME." >&2
    exit 1
fi

# O IsiX só carrega complementos com a assinatura intacta.
if ! codesign --verify --deep --strict "$TEMP/aberto/$NOME" 2>/dev/null; then
    echo "A assinatura do complemento baixado não confere; nada foi instalado." >&2
    exit 1
fi

mkdir -p "$DESTINO"
if [[ -d "$DESTINO/$NOME" ]]; then
    rm -rf "$DESTINO/$NOME.anterior"
    mv "$DESTINO/$NOME" "$DESTINO/$NOME.anterior"
fi
if ! ditto "$TEMP/aberto/$NOME" "$DESTINO/$NOME"; then
    rm -rf "$DESTINO/$NOME"
    [[ -d "$DESTINO/$NOME.anterior" ]] && mv "$DESTINO/$NOME.anterior" "$DESTINO/$NOME"
    echo "Falha ao copiar; a versão anterior foi mantida." >&2
    exit 1
fi
rm -rf "$DESTINO/$NOME.anterior"

VERSAO="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$DESTINO/$NOME/Contents/Info.plist" 2>/dev/null || echo "?")"
echo "NeuroLaudo $VERSAO instalado. Abra o IsiX DICOM Viewer."
echo "Para conferir: menu Plugins > Plugins Manager deve listar o NeuroLaudo."
