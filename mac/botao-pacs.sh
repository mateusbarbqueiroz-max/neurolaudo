#!/bin/bash
# Escolhe qual programa o botão "OsiriX" do PACS abre.
#
#   bash botao-pacs.sh ver      mostra o programa ligado hoje aos links osirix://
#   bash botao-pacs.sh isix     passa os links osirix:// para o IsiX DICOM Viewer
#   bash botao-pacs.sh osirix   devolve os links osirix:// ao OsiriX MD
#
# O botão do PACS é um link que começa com osirix://. O OsiriX MD e o IsiX se
# registram para esse tipo de link; o macOS entrega a um deles. Este script só
# troca essa escolha: não apaga nem altera nenhum dos dois programas.
#
# ATENÇÃO: ainda não foi executado em um Mac de verdade (escrito em Linux).
set -euo pipefail

ISIX_ID="thalesmms.isis.workstation"   # identificador do IsiX publicado no GitHub
ESQUEMA="osirix"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "Este script é para macOS." >&2
    exit 2
fi

programa_atual() {
    /usr/bin/osascript -l JavaScript -e '
        ObjC.import("AppKit");
        var url = $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL($.NSURL.URLWithString("osirix://teste"));
        url.isNil() ? "nenhum programa" : url.path.js;'
}

ligar_a() {
    local identificador="$1"
    /usr/bin/osascript -l JavaScript -e '
        function run(argv) {
            ObjC.import("CoreServices");
            ObjC.bindFunction("LSSetDefaultHandlerForURLScheme", ["int", ["id", "id"]]);
            return String($.LSSetDefaultHandlerForURLScheme($(argv[0]), $(argv[1])));
        }' "$ESQUEMA" "$identificador"
}

case "${1:-ver}" in
    ver)
        echo "Os links osirix:// abrem hoje: $(programa_atual)"
        ;;
    isix)
        if ! /usr/bin/osascript -e "id of app id \"$ISIX_ID\"" >/dev/null 2>&1; then
            echo "Não encontrei o IsiX DICOM Viewer instalado. Instale-o e abra uma vez antes." >&2
            exit 1
        fi
        codigo="$(ligar_a "$ISIX_ID")"
        if [[ "$codigo" != "0" ]]; then
            echo "O macOS recusou a troca (código $codigo)." >&2
            exit 1
        fi
        echo "Pronto. Os links osirix:// abrem agora: $(programa_atual)"
        ;;
    osirix)
        if ! OSIRIX_ID="$(/usr/bin/osascript -e 'id of app "OsiriX MD"' 2>/dev/null)"; then
            echo "Não encontrei o OsiriX MD instalado." >&2
            exit 1
        fi
        codigo="$(ligar_a "$OSIRIX_ID")"
        if [[ "$codigo" != "0" ]]; then
            echo "O macOS recusou a troca (código $codigo)." >&2
            exit 1
        fi
        echo "Pronto. Os links osirix:// abrem agora: $(programa_atual)"
        ;;
    *)
        sed -n '2,7p' "$0"
        exit 2
        ;;
esac
