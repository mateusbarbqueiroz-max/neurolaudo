# Guia: instalar o IsiX e ligar o botão do PACS

Tempo: cerca de 20 minutos. Nada aqui altera ou apaga o OsiriX MD.

O que eu conferi no código-fonte do IsiX: ele se registra para os links
`osirix://` e aceita todos os comandos de link do OsiriX, inclusive o de baixar
exames (`DownloadURL`). O que **não** conferi: nada disto foi executado em um
Mac. O teste de verdade é o seu.

## Passo 1 — Instalar o IsiX

1. Abra <https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/releases>.
2. Na versão mais recente (6.0.3 em 13/11/2026), abra **Assets** e baixe o
   arquivo `.zip` de **Apple Silicon** (tem `arm64` no nome).
3. Dê dois cliques no `.zip`. Arraste **IsiX DICOM Viewer** para a pasta
   **Aplicativos**.
4. Abra o IsiX. O macOS pergunta se pode abrir um programa baixado da internet:
   confirme.

O IsiX cria um banco de dados próprio (pasta `IsiX Data`). Se ele avisar que
encontrou um banco do Horos ou do OsiriX, é só um aviso: ele não abre nem
altera esse banco.

## Passo 2 — Ver qual programa o botão do PACS abre hoje

Com o OsiriX MD e o IsiX instalados, os dois disputam o botão. Para saber quem
está ganhando:

1. Abra o **Terminal** (⌘ + espaço, digite `Terminal`, Enter).
2. Cole o comando abaixo e aperte Enter.

```bash
osascript -l JavaScript -e 'ObjC.import("AppKit"); $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL($.NSURL.URLWithString("osirix://teste")).path.js'
```

A resposta é o caminho de um programa. Se terminar em `IsiX DICOM Viewer.app`,
pule para o Passo 4.

## Passo 3 — Passar o botão para o IsiX

Se a resposta foi o OsiriX, cole este comando no Terminal:

```bash
osascript -l JavaScript -e 'ObjC.import("CoreServices"); ObjC.bindFunction("LSSetDefaultHandlerForURLScheme", ["int", ["id", "id"]]); $.LSSetDefaultHandlerForURLScheme($("osirix"), $("thalesmms.isis.workstation"))'
```

A resposta esperada é `0`. Repita o comando do Passo 2 para confirmar.

Para **desfazer** e devolver o botão ao OsiriX MD:

```bash
OSIRIX_ID="$(osascript -e 'id of app "OsiriX MD"')" && osascript -l JavaScript -e 'function run(a) { ObjC.import("CoreServices"); ObjC.bindFunction("LSSetDefaultHandlerForURLScheme", ["int", ["id", "id"]]); return String($.LSSetDefaultHandlerForURLScheme($("osirix"), $(a[0]))); }' "$OSIRIX_ID"
```

Se algum comando der erro, copie a mensagem e me envie. Esta é a parte que eu
menos consegui verificar.

## Passo 4 — Testar o botão

1. Feche o OsiriX MD (os dois programas não devem ficar abertos juntos no teste).
2. No PACS do hospital, abra um exame e clique no botão do OsiriX.
3. Na primeira vez, o IsiX avisa que o suporte a links está desligado. Clique em
   **Activate & Restart**. Ele reinicia.
4. Clique no botão do PACS de novo.

O que pode acontecer:

| Resultado | O que significa |
| --- | --- |
| O exame baixa e abre no IsiX | Funcionou. Etapa 1 concluída. |
| O IsiX vem para a frente, mas nada baixa | O link pede para buscar o exame no PACS por DICOM. Falta o Passo 5. |
| Aparece uma mensagem de erro | Me envie o texto da mensagem. |
| Abre o OsiriX | O Passo 3 não pegou. Me avise. |

## Passo 5 — Só se o exame não baixou

Alguns PACS mandam um link que diz "busque este exame no servidor". Nesse caso
o IsiX precisa conhecer o servidor, como o OsiriX conhece.

1. No OsiriX MD, abra **Preferências > Locations** e anote do servidor do
   hospital: nome, endereço, AE Title e porta.
2. Ainda no OsiriX MD, em **Preferências > Listener**, anote o AE Title e a
   porta do próprio OsiriX.
3. No IsiX, em **Settings > Locations**, crie o servidor com os mesmos dados e
   o **mesmo nome**.
4. No IsiX, em **Settings > Listener**, use o mesmo AE Title e a mesma porta
   que o OsiriX usa.
5. Com o OsiriX MD fechado, teste o botão de novo.

## O que eu preciso que você me conte

1. O que aconteceu no Passo 4.
2. O **formato** do link do botão, sem dados de paciente. Como obter:
   clique com o botão direito no botão do PACS, escolha **Copiar link**, cole
   em um editor de texto e troque por `XXX` tudo o que vier depois de cada `=`,
   menos o nome do comando. Exemplo do que enviar:

   ```
   osirix://?methodName=DownloadURL&Display=XXX&URL=XXX
   ```

   Não envie o link original: ele contém identificação do paciente e o
   endereço do servidor do hospital.
3. Os **nomes das séries** dos seus exames de rotina (RM de encéfalo e TC de
   crânio), como aparecem na lista do visualizador, por exemplo `AX FLAIR`,
   `DWI b1000`, `ADC`, `SWI`, `SAG T1 MPRAGE`. São nomes de protocolo, não
   dados de paciente. Preciso deles para montar os protocolos de exibição.

## Opcional — trazer exames antigos

No IsiX: **File > Import > Import Studies from Horos or OsiriX…**. Ele copia os
estudos para o banco dele e não mexe no banco do OsiriX.

## Lembrete

O IsiX não declara certificação para diagnóstico. Para laudo diagnóstico, o
OsiriX MD continua sendo o seu visualizador certificado.
