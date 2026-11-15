# NeuroLaudo — neurorradiologia sobre o IsiX DICOM Viewer

## Situação em 15/11/2026, após a primeira noite

Tudo abaixo está em git local (`/home/user/neurolaudo`, 5 commits).
**Nada está salvo fora desta sessão ainda.**

Feito e conferido aqui (Linux):
- Rascunho reorganizado em `engine/`; os 9 testes Python passam.
- Código-fonte do IsiX lido (`docs/FATOS-ISIX.md`): ele se registra para
  `osirix://` e aceita todos os comandos de link do OsiriX, inclusive
  `DownloadURL`. Tem protocolos de exibição nativos, com ordem de séries e
  exames comparativos.
- `docs/GUIA-INSTALACAO.md`: passo a passo para o usuário.
- Complemento (`plugin/`): janelas de TC (menu e ⌃⌥ + número), índice de Evans,
  desvio da linha média, ABC/2, ASPECTS, protocolo de neuro e comparar com
  exame anterior. 46 testes Swift passam em Linux contra uma imitação do kit do IsiX.

Escrito, mas não conferido:
- Telas (`plugin/NeuroLaudo/Sources/UI/AppKitPresenter.swift`): só a sintaxe.
- `mac/botao-pacs.sh` e os comandos do guia: nunca executados em macOS.
- O complemento nunca foi compilado em macOS.

Descobertas que mudam o plano:
- Esta sessão não consegue criar repositório no GitHub; o usuário precisa criá-lo.
- Protocolos de exibição e comparação existem nativamente no IsiX (preferência
  `HANGINGPROTOCOLS`); os comandos do complemento são um apoio.
- O kit de plugins foi compilado com Swift 6.4.2: o servidor Mac precisa de Xcode recente.

Próximos passos, em ordem:
1. Entregar um `.zip` do projeto na conversa, como cópia de segurança.
2. Com o repositório criado: anexar, enviar, criar `.github/workflows/plugin.yml`,
   compilar em macOS, corrigir os erros e publicar o `.isixplugin`.
3. `mac/instalar.sh`: instalação do complemento por um comando.
4. `CLAUDE.md` e `docs/PLANO.md`: memória do projeto.
5. Motor de volumetria: normas, relatório e saída DICOM.
6. Protocolos nativos do IsiX configurados com os nomes reais das séries.

Depende do usuário:
- Criar o repositório `neurolaudo` no GitHub (público, recomendado, ou privado)
  e dar acesso ao Claude em claude.ai/connect-github.
- Seguir `docs/GUIA-INSTALACAO.md`: instalar o IsiX e testar o botão do PACS.
- Enviar o formato do link do botão (sem dados de paciente) e os nomes das séries.

## Contexto

O usuário é neurorradiologista, usa o OsiriX MD em um Mac Apple Silicon (16 GB+)
e não mexe em código: eu construo, ele testa. Ele quer um programa no estilo do
OsiriX dedicado à neurorradiologia. O que ele definiu:

- O coração é a **imagem**, e ela vem **primeiro**.
- A base deve ser da família OsiriX de código aberto. O "irisdicom" que ele citou
  foi identificado como **IsiX DICOM Viewer**, derivado ativo do Horos.
- Primeiros recursos de imagem: medidas de neuro, janelas de neuro, protocolos
  de exibição e comparação com exame anterior.
- Depois: **volumetria tipo NeuroQuant**; por último, laudo.
- O botão "OsiriX" do PACS do hospital abre o OsiriX sozinho (link `osirix://`);
  ele quer que abra o nosso programa.
- Trabalho **só pela nuvem**: sem Xcode no Mac dele.

## O que será entregue, em ordem

1. IsiX instalado no Mac e o botão do PACS abrindo nele (configuração, sem código).
2. Complemento "NeuroLaudo" dentro do IsiX: janelas de neuro, medidas de neuro,
   protocolos de exibição, comparação com anterior.
3. Volumetria cerebral com percentil por idade e sexo.
4. Laudo.

## Como vamos trabalhar

- Eu escrevo o código nesta sessão em nuvem e envio ao GitHub.
- Servidores Mac do GitHub compilam o complemento e, se der, abrem o IsiX com
  ele e me devolvem capturas de tela.
- O usuário instala cada versão colando **um comando** no Terminal, testa e me
  conta o que viu. Capturas de tela só do exame de teste, nunca de pacientes.
- Limite: não vejo o programa no Mac dele; o ciclo é mais lento que no Mac.

## Esta noite, sem depender do usuário

Autorização dada em 15/11/2026: seguir sem confirmações no que for possível.

- Reorganizar o rascunho e fazer os testes passarem.
- Tentar criar o repositório **privado** `neurolaudo` na conta do GitHub já
  conectada e enviar o código. Se a conexão não permitir, guardar em git local
  e entregar um `.zip` na conversa, para nada se perder.
- Ler o código-fonte do IsiX e do modelo de plugin; escrever o guia de instalação.
- Escrever o complemento (janelas e medidas de neuro; investigar protocolos e
  comparação) e a compilação nos servidores Mac do GitHub (usa a cota gratuita).
- Adiantar o motor de volumetria no que não exige o FreeSurfer.
- Relatório de manhã: o que ficou pronto, o que foi verificado e o que não foi.

## Fica para o usuário, de manhã

- Confirmar que "irisdicom" é o IsiX DICOM Viewer.
- Repositório público ou privado.
- Instalar o IsiX e testar o botão do PACS, seguindo o guia.
- Informar o formato do link do botão, sem dados de paciente.
- Aprovar downloads fora da rede liberada, se forem necessários.

## Decisões

- IsiX **usado como está**; a parte de neuro é um complemento `.isixplugin`
  (Swift). O IsiX muda quase todo dia; uma cópia modificada ficaria para trás e
  perderia a notarização. Derivar um programa próprio fica para depois, se o
  complemento não bastar (a licença permite, com outro nome e ícone).
- Sem engenharia reversa do OsiriX MD (fechado e proprietário).
- Volumetria local no Mac: SynthSeg 2.0 + normas públicas do Neurodesk.
- Nenhum exame real nesta sessão. Testes com fantoma sintético e dados públicos.
- Resultados de volumetria rotulados "uso em pesquisa, não validado para diagnóstico".
- O visualizador Qt do rascunho é descartado; fica só o que serve ao motor.
- Trabalho direto no ramo principal do repositório, sem pull requests.
- A decidir na Etapa 0: repositório **público** (recomendado: compilação gratuita
  sem limite e instalação por um comando; sem dados de paciente no código) ou
  privado (cota de compilação limitada e instalação menos simples).

## Etapas

### Etapa 0 — Repositório e memória do projeto
- Usuário cria o repositório `neurolaudo` no GitHub e dá acesso ao Claude; eu
  anexo e envio o primeiro commit.
- `CLAUDE.md` e `docs/PLANO.md`: decisões, fatos e regras, para sessões futuras.
- Reorganizar o rascunho: `neurolaudo/` → `engine/neurolaudo/`; remover `ui/`,
  `__main__.py`, `reports/export.py`, `tests/test_ui.py` e a dependência do Qt.
- Fazer `pytest` passar pela primeira vez no que sobrar.

### Etapa 1 — Base de imagem e botão do PACS
- Ler o código-fonte do IsiX (clonar e procurar `methodName`) para listar os
  comandos de link aceitos. `DownloadURL` não está na documentação.
- `docs/GUIA-INSTALACAO.md`, passo a passo com o que clicar: instalar o IsiX
  6.0.x (arm64), ativar links em Settings > Listener, importar exames por
  File > Import sem abrir o banco do OsiriX no lugar.
- `mac/set_osirix_handler.sh`: torna o IsiX o destino dos links `osirix://`;
  reversível. Testado antes no servidor Mac do GitHub.
- Usuário me passa o **formato** do link do botão (nome do comando e dos
  parâmetros, sem valores de paciente) e testa o clique.
- Se o IsiX não entender o link: `mac/url_forwarder/`, miniaplicativo que recebe
  `osirix://`, baixa o exame e entrega ao IsiX.

### Etapa 2 — Complemento de neuro
- **2a. Esqueleto e esteira.** `plugin/` a partir do IsiXPluginTemplate;
  `.github/workflows/plugin.yml` (compila, roda `script/verify_bundle.py`,
  publica o `.isixplugin`); `mac/instalar.sh` (baixa e instala em
  `~/Library/Application Support/IsiX/Plugins`). Tentativa, com tempo limitado,
  de teste automático: IsiX + complemento + fantoma no servidor Mac, com captura
  de tela e registro de autoteste.
- **2b. Janelas de neuro.** Encéfalo, AVC, subdural, osso, angio-TC, seios da
  face. Valores de `imaging/windowing.py` (`CT_PRESETS`). Preferir os presets
  nativos do IsiX (com atalho); comandos do complemento como apoio.
- **2c. Medidas de neuro.** ABC/2, índice de Evans, desvio da linha média,
  ASPECTS, a partir das medidas feitas na imagem. Cálculo em `core/` (Swift
  puro, com testes), portado de `reports/calculators.py`.
- **2d. Protocolos de exibição e comparação com anterior.** Começa por uma
  investigação: a API v1 não documenta abrir nem organizar janelas. Rotas, em
  ordem: SDK e ponte de plugins antigos; comandos XML-RPC locais
  (`DisplayStudy` e afins); recursos nativos do IsiX; pedido ao mantenedor.
  A comparação exige o exame anterior já no banco local.

### Etapa 3 — Volumetria tipo NeuroQuant
- `engine/neurolaudo/volumetry/`: `select.py` (série T1 3D elegível), `nifti.py`
  (geometria a partir de IOP/IPP), `engine.py` (`mri_synthstrip` +
  `mri_synthseg --fast --cpu --vol`), `norms.py` (z e percentil), `report.py`
  (tabela e curvas por idade), `dicom_out.py` (mapa colorido e páginas como DICOM).
- `engine/neurolaudo/cli.py`: `neurolaudo volumetria <pasta>`.
- Reaproveitar `dicom/loader.py` (`scan_folder`, `load_volume`, `_slice_position`),
  estendendo `Volume` com geometria e mapa corte→arquivo.
- Comando "Volumetria cerebral" no complemento: exporta a série, roda o motor em
  segundo plano, importa o resultado, mostra a tabela.
- No Mac: FreeSurfer 8.2 (instalador oficial, registro gratuito) e o motor.

### Etapa 4 — Laudo
- Modelos de `reports/templates.py` revisados pelo usuário; inserção de medidas
  e da volumetria; PDF.

## Verificação

- **Lógica**: testes de `core/` (Swift) e `engine/` (`pytest`) a cada envio.
- **Complemento**: compila no servidor Mac; `verify_bundle.py` passa; aparece em
  Plugins > Plugins Manager; comandos conferidos no fantoma
  (`scripts/make_phantom.py`) por captura de tela automática ou pelo usuário.
- **Botão do PACS**: usuário clica e o exame abre no IsiX.
- **Normas**: aplicar o modelo ao CSV público do IXI; esperar cerca de 90 % dos
  sujeitos entre os percentis 5 e 95 e z com média ~0 e desvio ~1.
- **Volumetria no Mac**: casos conhecidos (normais e com atrofia) e, se houver,
  comparação com laudos do NeuroQuant dos mesmos exames.

## Riscos e limites

- O IsiX é de um mantenedor só; a API de plugins v1 saiu em 12/11/2026 e pode
  mudar. Fixar a versão do IsiX e atualizar com critério.
- Protocolos de exibição e comparação podem não caber na API atual.
- OsiriX MD e IsiX disputam o link `osirix://` e a porta DICOM.
- IsiX e NeuroLaudo não têm certificação: apoio, não diagnóstico. Os percentis
  não equivalem aos do NeuroQuant; diferença entre aparelhos de até ~0,5 DP;
  normas só para 20–86 anos.
- Complemento sem assinatura de desenvolvedor Apple: instalação por comando no
  Terminal. Assinatura e notarização exigiriam conta paga da Apple.
- Rede desta sessão é limitada; alguns downloads pedirão aprovação do usuário.

## Referências (pesquisa de 15/11/2026)

- IsiX: github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS (ramo `horos`). LGPLv3;
  macOS 15+; versões assinadas e notarizadas; 6.0.3 em 13/11/2026. Links
  `horos://`/`osirix://` e XML-RPC na porta 8080, ligados em Settings > Listener;
  documentados `retrieve`, `DisplayStudy`, `CMove`.
- Modelo de plugin: github.com/ThalesMMS/IsiXPluginTemplate (MIT; SDK LGPLv3).
  API v1: comandos de menu; leitura de visualizadores, séries, imagens, geometria
  e pixels; gravar pixels e janela; ROIs; ler banco; importar arquivos; tarefas
  em segundo plano; janelas próprias. Xcode 16+; `script/build.sh`,
  `script/install.py`, `script/verify_bundle.py`; docs em `SDK/README.md`.
- Normas: github.com/neurodesk/neurocontainers, `recipes/synthseg/`
  (`brainquant_norms.json`, `brainquant_ixi_volumes.csv`,
  `fit_brainquant_norms.py`, `BRAINQUANT_NORMS.md`). MIT; dados do IXI,
  CC BY-SA 3.0. 561 adultos, 20–86 anos. Modelo:
  `ln V = b0 + b1·a + b2·a² + c·ln(ICV/1500 mL)`, `a = (idade − 50)/10`,
  `ln σ(a) = g0 + g1·a`.
- Horos: github.com/horosproject/horos (LGPL-3.0). OsiriX aberto antigo:
  github.com/pixmeo/osirix.
- Ambiente: Linux, 4 CPUs, 15 GB, sem GPU; não compila nem executa programas de Mac.
