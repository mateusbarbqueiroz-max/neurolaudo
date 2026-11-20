# Fatos sobre o IsiX DICOM Viewer (lidos do código-fonte)

Levantado em 15/11/2026 no commit `3e24831` (ramo `horos`, 13/11/2026) de
`github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS` e no commit `c963675` de
`github.com/ThalesMMS/IsiXPluginTemplate`. Conferir de novo quando o IsiX mudar
de versão: ele muda quase todo dia.

## Identidade

| Item | Valor | Onde |
| --- | --- | --- |
| Nome do aplicativo | `IsiX DICOM Viewer.app` | `script/build_release.sh` |
| Identificador (versão do GitHub) | `thalesmms.isis.workstation` | `Horos/Horos.xcconfig` |
| Preferências | domínio = identificador acima | `UserDefaults` padrão |
| Pasta de plugins | `~/Library/Application Support/IsiX/Plugins` | `SDK/README.md` |
| AE Title padrão | nome do computador (até 16 letras) ou `ISIX` | `DefaultPreferencesTests.swift` |
| Porta DICOM padrão | 11112 | `RemoteDataNodeIdentifier.swift` |

## Links `osirix://` e `horos://`

- `Horos/Info.plist` registra **os dois** esquemas (`horos` e `osirix`).
- Tratamento em `Horos/Sources/ExternalRequestHandler.swift`.
- Se o suporte a URL estiver desligado (preferência `httpXMLRPCServer`, padrão
  desligado), o clique mostra um aviso com o botão **"Activate & Restart"**.
  O mesmo ajuste fica em Settings > Listener. Porta XML-RPC:
  `httpXMLRPCServerPort`, padrão 8080.
- Comandos aceitos, sem diferenciar maiúsculas
  (`Modules/IsiXHTTPServer/Sources/XMLRPCMethodTable.swift`):

| Comando | Parâmetros |
| --- | --- |
| `DownloadURL` | `URL` (arquivo .dcm, .zip ou WADO), `Display` (opcional; exige WADO com `studyUID`) |
| `DisplayStudy` | `PatientID`, `StudyInstanceUID`, `AccessionNumber`, `StudyID` |
| `DisplaySeries` | `PatientID`, `SeriesInstanceUID` |
| `FindObject` / `DBWindowFind` | `request`, `table`, `execute` |
| `Retrieve` | `serverName`, `filterKey`, `filterValue` |
| `CMove` | `accessionNumber`, `server` |
| `CloseAllWindows` | nenhum |
| `Close2DViewerWithSeriesUID` / `Close2DViewerWithStudyUID` | `uid` |
| `GetDisplayed2DViewerSeries` / `GetDisplayed2DViewerStudies` | nenhum |
| `DisplayStudyListByPatientName` / `DisplayStudyListByPatientId` | `PatientName` / `PatientID` |
| `SelectAlbum` | `name` |
| `OpenDB` | `path` |
| `SwitchToDefaultDBIfNeeded` | nenhum |
| `PathToFrontDCM` | `onlyfilename` |
| `KillOsiriX` | nenhum |

- Um link que termina em `.xml` sem comando é tratado como manifesto WADO.
- `Retrieve` e `CMove` precisam do PACS cadastrado em Settings > Locations com o
  mesmo nome que o link usa em `serverName`/`server`.

## Janelas (window level)

- Presets nativos na preferência `WLWW3`: dicionário nome → `[nível, largura]`.
- De fábrica: `CT - Brain` (50/100), `CT - Bone`, `CT - Pulmonary`, `CT - Abdomen`...
- Teclas 1 a 9 aplicam os presets (preferência de hot keys); `~` volta ao padrão.

## Protocolos de exibição nativos

- Preferência `HANGINGPROTOCOLS`: dicionário modalidade → lista de protocolos.
  O primeiro da lista é o padrão da modalidade. Os demais valem quando o campo
  `Study Description` do protocolo aparece na descrição do estudo (sem diferenciar
  maiúsculas). Código: `Horos/Sources/WindowLayoutManager.swift`.
- Campos (`Horos/Sources/ViewerOpener.swift`):

| Campo | Sentido |
| --- | --- |
| `Study Description` | texto procurado na descrição do estudo |
| `WindowsTiling` | grade de janelas: valor = (linhas − 1) × 4 + (colunas − 1); 1000 = todas |
| `ImageTiling` | grade de imagens dentro de cada janela |
| `SeriesOrder` | termos separados por vírgula; para cada termo, a **última** série cujo nome o contém; depois as demais |
| `SeriesOrderIgnoreCase` | ignora maiúsculas nos termos |
| `NumberOfComparativeToDisplay` | quantos exames anteriores abrir |
| `NumberOfSeriesPerComparative` | séries de cada anterior (mínimo 1) |
| `PreviousStudySameModality` / `PreviousStudySameDescription` | filtro dos anteriores |
| `Sync` | sincroniza a rolagem por posição |
| `Propagate` | propaga ajustes entre janelas |
| `WL` / `WW` | janela inicial (0/0 = padrão; 1/1 = faixa completa) |
| `RepeatSeriesIfNotEnoughSeries` | repete séries para preencher a grade |

- Exemplo de fábrica (mamografia): `WindowsTiling = 5` (2 × 2),
  `SeriesOrder = "R CC,L CC,R MLO,L MLO"`, `NumberOfSeriesPerComparative = 4`.
- Auto-organização de janelas: preferência `AUTOTILING`.

## API de plugins v1 (`IsiXPluginKit`)

Interface exata em
`plugin/SDK/IsiXPluginKit.framework/Versions/A/Modules/IsiXPluginKit.swiftmodule/arm64-apple-macos.swiftinterface`.
Compilada com Swift 6.4.2. Resumo do que importa para a neuro:

- Comandos de menu: `context.register(IsiXCommand(id:title:placement:requirement:))`.
  Locais: `.imageFilters`, `.roiTools`, `.database`, `.other`. Sem atalho de teclado.
- Visualizador (`IsiXViewer`): `series()`, `image()`, `geometry()`, `attributes()`,
  `windowLevel()`, `setWindowLevel(_:)`, `rois()`, `addROI(_:)`, `updateROI(_:_:)`,
  `removeROI(_:)`, `statistics(of:)`, `setCurrentSlice(_:)`, `addOverlay(_:)`.
- ROIs que se pode criar: ponto, linha, retângulo, oval, polígono, polilinha,
  pincel (máscara). Texto e ângulo só se leem.
- Banco (`IsiXDatabase`): `studies(matching:)`, `series(inStudy:)`,
  `images(inSeries:)`, **`openViewer(forSeries:)`**, `importFiles(at:)`,
  `writeDerivedSeries(_:)`.
- Eventos: `viewerOpened`, `viewerWillClose`, `sliceChanged`, `roiChanged`, `imagesAdded`.
- Entrada: `interceptInput` (clique, arrasto e teclas sobre a imagem).
- Rede: `find` (C-FIND) e `send`; **não há buscar/retirar (C-MOVE)** na API,
  mas o link `horos://?methodName=retrieve...` faz isso.
- Não há como fechar janelas nem definir a grade pela API; os comandos
  XML-RPC `CloseAllWindows` e `Close2DViewerWith...` existem.

## Compilação do plugin

- macOS 15+, Xcode 16+. `plugin/script/build.sh --configuration Release`.
- O projeto Xcode usa pasta sincronizada: todo arquivo `.swift` dentro de
  `plugin/NeuroLaudo/` entra no alvo sem editar o projeto.
- Assinatura ad hoc por padrão; a versão do IsiX publicada no GitHub desliga a
  validação de bibliotecas para aceitar plugins de terceiros.
- `script/run-isolated.sh` só funciona com o aplicativo de desenvolvimento
  (identificador terminado em `.local-development`), que é compilado do código-fonte.

## O link do botão do PACS do usuário

Formato (o identificador do exame e o nome do servidor não ficam no repositório):

    osirix://?methodName=Retrieve&retrieveOnlyIfNeeded=yes&ServerName=XXX
        &filterKey=StudyInstanceUID&filterValue=XXX&then=Open

O que o IsiX faz com cada parte (`Horos/Sources/XMLRPCInterface+Retrieve.swift`,
`Horos/Sources/HorosSchemeURL.swift`, `Horos/Sources/RISRequestServers.swift`).
A coluna da direita vale a partir da 6.0.4, feita pelo autor depois do pedido
[ThalesMMS/IsiX-DICOM-Viewer-macOS#48](https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/issues/48)
(lido no código da 6.0.6, commit `c6a718f`, e no README do IsiX):

| Parte | 6.0.3 | 6.0.4 em diante |
| --- | --- | --- |
| `methodName=Retrieve` | aceito | aceito; o nome `methodName` é escrito exatamente assim |
| Aspas em volta dos valores | removidas | removidas |
| `ServerName` / `serverName` | só `serverName`; `ServerName` dava "server name is empty" | os nomes dos parâmetros valem em qualquer caixa |
| Nome do servidor | igual à descrição em Locations | a descrição em Locations ou o AE Title do servidor, exatos ou sem diferença de caixa |
| `filterKey=StudyInstanceUID` | aceito (até nove filtros) | aceito; o nome do atributo tem de estar escrito certo, senão o pedido não é enviado |
| `retrieveOnlyIfNeeded=yes` | ignorado: buscava de novo | não busca o exame que já está completo no Mac (compara com o número de imagens que o servidor informa; se o servidor não informa, busca) |
| `then=Open` | ignorado: o exame chegava e não abria | abre o exame assim que chega a primeira série (confere a cada meio segundo, espera até 30 s, ajustável em `XMLRPCRetrieveOpenWaitSeconds`); `then=select` só seleciona na lista |
| `retrieveMode` | aceito (opcional) | aceito (opcional) |

A busca é DICOM (C-FIND e depois C-MOVE ou C-GET): o servidor precisa estar em
Settings > Locations, e o AE Title do IsiX é o destino do C-MOVE.

Desde a 6.0.4, quem abre o exame do link é o próprio IsiX. A abertura automática
do complemento (`plugin/NeuroLaudo/Sources/Glue/AutoOpen.swift`) espera 3 s depois
do fim do recebimento e não abre nada se o exame já estiver aberto; continua
valendo para exames que chegam sem link.

Desde a 6.0.5 o IsiX também declara o esquema `isix://`. Ao abrir, se os links
estão ligados e outro programa (o OsiriX MD, por exemplo) abre os links
`osirix://`, ele mostra um painel "Another application opens the links of IsiX
DICOM Viewer", com os botões **Make IsiX the Default** e **Not Now** e as opções
**Always at startup** e **Don't ask again** (`Horos/Sources/LinkSchemeStartupCheck.swift`).
Em Settings > Listener escolhe-se quais dos três esquemas o IsiX abre.

## Porta de comandos (XML-RPC)

- Uma só opção, **Activate the URL support and HTTP XML-RPC Server on port**, liga
  os links e um servidor HTTP na porta 8080.
- Valor de fábrica de `httpXMLRPCServerAccessScope`: `2` (qualquer endereço), sem
  senha. Registro de uma instalação nova (6.0.3, servidor Mac): "answering this Mac
  and any address, WITHOUT a password". Na 6.0.6 o valor de fábrica continua `2`
  (`Modules/IsiXPreferences/Sources/NetworkPreferences.swift`); agora o README do
  IsiX o descreve, e o painel Listener avisa em vermelho.
- Valores: `0` só este Mac, `1` rede local, `2` qualquer endereço. No painel:
  **Answer messages from** → **This Mac only**, **Computers on the local network**,
  **Any address**; e **Require a user name and password from other computers**.
- Com `0`, o registro passa a "answering this Mac only". Os links continuam
  funcionando: chegam ao IsiX como evento do próprio Mac, sem passar pelo servidor
  (o README do IsiX recomenda **This Mac only** para quem só usa links).
- O servidor publica `dbwindowfind` (o conteúdo do banco, com nomes e
  identificadores de pacientes), `DownloadURL`, `Retrieve` e `KillOsiriX`. Na 6.0.6,
  pedidos vindos de páginas da internet são recusados e `FindObject` com
  `execute = Delete` pede confirmação no Mac.
- O autor pediu que observações de segurança vão pelo canal privado do GitHub
  (aba Security do repositório dele, "Report a vulnerability"), ou por e-mail ou
  LinkedIn indicados no perfil dele. Em 20/11/2026 o canal privado não estava
  ligado no repositório (a página dá erro 404 e a aba Security só diz "No security
  policy detected"); sobram o e-mail e o LinkedIn do perfil.

## Conferido no servidor Mac do GitHub (15/11/2026)

Imagem `xcode-27-arm64`, macOS 27.0.1, Xcode 27.2, IsiX 6.0.3 notarizado.
Fluxo em `.github/workflows/isix.yml`.

- O complemento compila (arm64 e x86_64) e passa em `verify_bundle.py` ("loadable").
- `mac/instalar.sh` baixa e instala o complemento.
- `mac/botao-pacs.sh` roda sem erro e deixa o IsiX como destino de `osirix://`
  (sem OsiriX MD na máquina para disputar).
- O IsiX carrega o complemento: "Registering IsiX plugin app.neurolaudo.isixplugin
  0.1.0 (API 1)" e, do complemento, "NeuroLaudo 0.1.0 ativado, 14 comandos".
- Os 14 comandos aparecem no menu Plugins: seis janelas em Image Filters; quatro
  medidas em ROI Tools; três em Database; a ajuda em Others.
- Ao importar o fantoma, o complemento registra "exame recebido aberto: 1 série(s)".
- Na primeira abertura, o macOS pergunta se o IsiX pode encontrar dispositivos
  na rede local. Sem permitir, ele não alcança o PACS.
- Ao abrir uma pasta pelo Finder, o IsiX pergunta "Copy Files" ou "Copy Links".

- A abertura automática abre de fato um visualizador 2D com a série do fantoma
  ("Axial 2.5mm"), conferido por captura de tela.
- O atalho ⌃⌥4 do complemento aplica a janela de osso: o visualizador passa de
  "WL: 40 WW: 80" para "WL: 600 WW: 2800" e o registro mostra "janela aplicada: Osso".

Particularidade do servidor: as janelas do IsiX existem, mas só aparecem na tela
depois do comando de menu Window > Tile 2D Viewer Windows (o aplicativo é aberto
em segundo plano). As capturas ficam na versão `teste-isix` do repositório.

Conferido em 16/11/2026, no mesmo servidor:

- **Medidas.** O autoteste do complemento (`Glue/SelfTest.swift`, comando que só
  existe com `-NeuroLaudoAutoteste YES`) desenhou as marcas pelo kit e leu de
  volta: 5 de 5 conferências passaram.
  - Linha de 120 mm: NeuroLaudo 120,00 mm e a medida do próprio IsiX 120,00 mm.
  - Índice de Evans 0,35; desvio da linha média 6,0 mm para a esquerda, com as
    marcas rotuladas; ABC/2 6,00 mL (intervalo entre cortes de 2,50 mm lido da
    série); janela 600/2800 aplicada e lida de volta.
- **Protocolo de RM.** Ao chegar o exame de teste de RM, o complemento abriu as
  seis séries na ordem FLAIR, difusão, ADC, SWI, T1 e T1 pós-contraste; captura
  de tela com as seis janelas lado a lado.
- **Comparação com exame anterior.** Com um exame anterior do mesmo paciente no
  banco, o comando abriu a série equivalente (de oito para nove janelas).

Ainda não exercitado dentro do IsiX (em 16/11/2026 de manhã): o painel do
ASPECTS, as medidas com linhas desenhadas à mão e exames reais, cujos nomes de
série podem diferir dos do exame de teste. O aviso com botão Copiar foi visto
à tarde, no teste da volumetria (abaixo).

Conferido em 16/11/2026 (tarde), no mesmo servidor, com o exame de teste de T1
volumétrico (`make_phantom.py --t1`):

- **Volumetria, caminho do complemento.** O comando *Volumetria cerebral
  (pesquisa)…* copiou os 96 cortes da série aberta para um arquivo de volume,
  chamou o motor em Python como processo à parte, e o motor leu do arquivo a
  mesma orientação que o complemento tinha calculado ("PIR"). Registro:
  "volumetria: série copiada, 96 cortes, orientação PIR" e, seis segundos
  depois, "volumetria: concluída".
- **Séries gravadas pelo kit.** `writeDerivedSeries` seguido de `importFiles`
  pôs no exame duas séries novas: "NeuroLaudo: volumetria (pesquisa)", com 2
  imagens, e "NeuroLaudo: mapa da segmentação (pesquisa)", com 96 imagens na
  mesma posição dos cortes do T1 (o visualizador mostra as mesmas coordenadas
  nas duas janelas). O IsiX copia paciente e exame da série de origem.
- **Aviso com o resumo.** A tela com a frase para o laudo e os botões Fechar e
  Copiar apareceu como esperado (captura `6-volumetria-resumo.png`).
- Neste teste só a segmentação era de mentira (rótulos por limiar); o restante
  do motor era o de verdade. A segmentação de verdade é testada à parte
  (`docs/VOLUMETRIA.md`).

Fatos do kit usados na volumetria (lidos da interface e do `SDK/README.md`):
`viewer.image(slice:)` devolve os pixels em ponto flutuante, linha por linha, e
a geometria de cada corte; o centro do pixel (coluna c, linha r) fica em
`imagePosition + rowDirection·(c·columnSpacing) + columnDirection·(r·rowSpacing)`;
`startTask` roda o trabalho fora da linha principal; gravar e importar séries
exige a capacidade `database.import` no `Info.plist`.

- **Posição da série nova.** Ao abrir o mapa colorido, o IsiX o posiciona no mesmo corte (mesma
  posição em milímetros) em que o T1 está, e os dois visualizadores mostram as mesmas coordenadas.
  A numeração dos cortes do mapa sai no sentido contrário ao do T1 (o IsiX ordena a série nova a
  seu modo), o que não atrapalha a correspondência por posição. Captura: `docs/volumetria-no-isix.png`.

## Botão do PACS simulado, IsiX 6.0.6 (20/11/2026)

No servidor Mac do GitHub, com um PACS de teste (`engine/scripts/fake_pacs.py`)
guardando um exame de RM do fantoma que o IsiX não tinha. O IsiX foi aberto com
o servidor cadastrado (descrição "PACS de teste", AE Title `PACSFALSO`) e com o
receptor DICOM ligado (AE Title `ISIXTESTE`, porta 11113). O link foi aberto no
formato do PACS do hospital, com `ServerName` maiúsculo, valores entre aspas e o
nome do servidor igual ao AE Title (não à descrição):

    osirix://?methodName='Retrieve'&retrieveOnlyIfNeeded='yes'&ServerName='PACSFALSO'
        &filterKey='StudyInstanceUID'&filterValue='<exame de teste>'&then=Open

- **Primeiro clique.** O IsiX consultou o PACS (C-FIND do exame, das 6 séries e
  das imagens) e pediu o exame por C-MOVE; as 96 imagens chegaram ao receptor. O
  IsiX abriu o exame sozinho: uma janela com a primeira série (AX FLAIR) e as 6
  séries na coluna da esquerda (`docs/botao-pacs-simulado.png`).
- **Complemento.** Registrou "exame recebido já estava aberto (pelo IsiX); nada
  aberto pelo complemento": não houve janelas a mais.
- **Segundo clique** no mesmo link. O IsiX consultou o PACS uma vez e não pediu o
  exame de novo ("XMLRPC Retrieve: every study found is whole here; nothing is
  retrieved"); o exame voltou a ser mostrado.

Também nesta rodada: ao importar o relatório e o mapa da volumetria no exame, a
abertura automática viu o exame já aberto e não abriu nada (antes da mudança,
abriria de novo o protocolo daquele exame).

Não conferido: o PACS do hospital (aparelho, rede, AE Titles reais) e o OsiriX MD
disputando o botão no mesmo Mac.
