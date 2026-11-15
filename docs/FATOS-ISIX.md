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
