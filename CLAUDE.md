# NeuroLaudo

Ferramentas de neurorradiologia sobre o IsiX DICOM Viewer, derivado aberto do
Horos/OsiriX. Plano aprovado em `docs/PLANO.md`.

## Quem usa e como falar

- O usuário é neurorradiologista e não programa. Fala português do Brasil.
  Explique sem jargão de programação; termos médicos estão liberados.
- O teste de verdade é em um Mac Apple Silicon com 16 GB ou mais, sem Xcode: o
  trabalho é só pela nuvem, com compilação nos servidores Mac do GitHub.
- **Até cerca de 4 de janeiro de 2027 não há Mac compatível.** O Mac atual é
  antigo demais para o IsiX; o novo, onde a esposa do usuário vai trabalhar,
  ainda não chegou. Até lá, o servidor Mac do GitHub é o único Mac disponível.
  Não peça ao usuário para instalar ou testar nada no Mac; registre em
  `docs/PENDENCIAS.md`.
- Repositório: `mateusbarbqueiroz-max/neurolaudo`, público.
- Para diagnóstico ele usa o OsiriX MD, que é certificado. O IsiX e o NeuroLaudo
  são apoio, sem certificação.
- Ele lauda por ditado de voz no Laudite (máscaras e frases prontas). O NeuroLaudo
  entrega texto para colar no laudo; não substitui o Laudite.

## Regras

- Nenhum exame real de paciente nesta sessão nem no repositório. Testes com o
  fantoma (`engine/scripts/make_phantom.py`) e com dados públicos. Capturas de
  tela só do fantoma.
- Sem engenharia reversa do OsiriX MD (fechado e proprietário).
- Resultados de volumetria rotulados "uso em pesquisa, não validado para diagnóstico".
- Trabalho direto no ramo principal, sem pull requests.
- Dizer sempre o que foi verificado e o que não foi. Código de macOS só conta
  como verificado depois de compilar no servidor Mac.
- O usuário tem limite de uso: ser econômico, evitar leituras longas repetidas.

## Estrutura

- `docs/PLANO.md`: plano aprovado. `docs/FATOS-ISIX.md`: fatos lidos do código
  do IsiX. `docs/GUIA-INSTALACAO.md`: guia do usuário.
- `plugin/`: complemento `.isixplugin` em Swift.
  - `NeuroLaudo/Sources/Core`: cálculo puro, sem IsiX nem AppKit.
  - `NeuroLaudo/Sources/Glue`: usa o IsiXPluginKit; sem telas.
  - `NeuroLaudo/Sources/UI`: telas em AppKit; só compila em macOS.
  - `SDK/`: kit do IsiX, copiado do modelo. Não editar.
  - `LinuxCheck/`: imitação do kit, só para conferir e testar em Linux.
  - `script/`, `Config/`, `NeuroLaudo.xcodeproj`: do modelo de plugin do IsiX.
- `engine/`: motor em Python.
  - `neurolaudo/volumetry/`: `pipeline.py` (recorte, SynthSeg, normas), `norms.py`,
    `report.py` e `overlay.py` (páginas), `volume.py` (NIfTI), `tables.py`, `cli.py`,
    `history.py` (histórico local e comparação com o exame anterior), `compare_report.py` (página dela).
    `data/repeticao.json`: limite de repetição medido por `volumetria.yml -f onde=repeticao`.
  - `tests/fakes/`: segmentador de mentira no lugar do SynthSeg.
  - `scripts/`: fantomas (`make_phantom.py`, `--rm`, `--t1`), validação e diagnóstico da volumetria.
- `mac/`: scripts para o Mac do usuário (`instalar.sh`, `botao-pacs.sh`, `instalar-volumetria.sh`).
- `docs/VOLUMETRIA.md`: como a volumetria funciona, o que foi medido e o que falta conferir.

## Comandos

- Testes do complemento em Linux: `cd plugin && swift test`.
- Testes do motor: `cd engine && python -m pytest -q`.
- Compilar o complemento: só em macOS, `plugin/script/build.sh --configuration Release`.
- Acionar testes no GitHub: `gh workflow run ARQUIVO.yml --ref main [-f chave=valor]` (sem `--ref` falha).
  `isix.yml`: complemento dentro do IsiX (roda sozinho toda segunda, com o IsiX mais novo; ver a
  última rodada antes de mexer no complemento). `volumetria.yml -f onde=linux|miniatura|ambos|diagnostico|repeticao`:
  segmentação de verdade em exames públicos.
- Ler o resultado: `gh api repos/DONO/REPO/actions/runs/ID/jobs` (passos), `.../actions/jobs/ID/logs`
  (registro) e os arquivos das versões `teste-isix` e `teste-volumetria` (baixar com `curl`).

## Armadilhas já encontradas

- A sessão em nuvem não cria repositórios no GitHub; o usuário cria.
- O site swift.org não é acessível daqui. Compilador Swift para Linux:
  `https://github.com/swiftwasm/swift/releases/download/swift-wasm-5.10.0-RELEASE/swift-wasm-5.10.0-RELEASE-ubuntu22.04_x86_64.tar.gz`
  (descompactar e pôr `usr/bin` no PATH).
- XCTest em Linux aborta com classe de teste `@MainActor`. Usar
  `MainActor.assumeIsolated`, como em `plugin/Tests/NeuroLaudoTests/GlueTests.swift`.
- Membros com "stub" no nome só existem na imitação do kit. O código em
  `plugin/NeuroLaudo/Sources` não pode usá-los:
  `grep -rn stub plugin/NeuroLaudo/Sources` deve voltar vazio.
- O banco de dados do kit tem versões síncrona e assíncrona com o mesmo nome;
  em função síncrona o Swift escolhe a síncrona.
- O kit foi compilado com Swift 6.4.2 e a interface usa a sintaxe `Módulo::Tipo`;
  o servidor Mac precisa de um Xcode recente para lê-la.
- O projeto Xcode usa pasta sincronizada: arquivos `.swift` dentro de
  `plugin/NeuroLaudo/` entram no alvo sem editar o projeto.
- O Mac compila em Swift 6 (erros de concorrência são erros). Em Linux o Swift 5.10 só avisa: ler os
  avisos de `swift build`. `weak self` dentro de fecho aninhado não passa; usar um fecho
  `@MainActor @Sendable` como em `NeuroLaudoPlugin.startVolumetry`. Avisos de `URL` não `Sendable`
  só existem em Linux.
- Nesta sessão `sleep` longo em primeiro plano é bloqueado e o GraphQL do GitHub não funciona
  (`gh release view`, `gh run view`): usar a API REST.
- Volumetria, medido em 16/11/2026 (detalhes em `docs/VOLUMETRIA.md`):
  - O `mri_synthseg` da instalação mínima precisa de `--noaddctab`. A opção `--qc` muda os volumes e
    estoura a memória: fica desligada.
  - O SynthStrip (PyTorch) não roda em Apple Silicon em tempo razoável: saiu do motor. O recorte é
    feito em dois passos (`volume.head_box`, depois `volume.brain_box`).
  - Qualquer mudança no recorte muda os volumes das estruturas pequenas em 1 a 3 % (ruído do
    SynthSeg). Mexer no recorte exige rodar de novo `volumetria.yml -f onde=linux` e comparar.
  - Em Linux, sem oneDNN e com 4 núcleos, o TensorFlow faz um pedido grande de memória que o Linux
    recusa (bad_alloc) embora use só 7 GB: os testes ligam `vm.overcommit_memory=1`. O macOS não recusa.
  - O servidor Mac do GitHub tem 7 GB: o exame inteiro não cabe; lá só se testa o recorte de 12 cm.
  - A biblioteca `surfa` só existe em código-fonte: a versão compilada para Mac fica na versão `motor`
    do repositório, publicada pelo próprio teste.
  - O IsiX abre a série nova no mesmo corte (posição) em que a série de origem está.
- IsiX 6.0.4 em diante abre sozinho o exame de um link com `then=Open` e aceita `ServerName`
  em qualquer caixa (`docs/FATOS-ISIX.md`). A API do GitHub não alcança o repositório do autor
  (nem para ler o pedido 48): ler a página pública com o agente web-fetch e o código com `git fetch`
  em `/home/user/refs/isix`.
- IsiX 6.0.7 separou os links (`-LinkSchemeSupport YES`) da porta de comandos (`httpXMLRPCServer`);
  sem os links ligados, o primeiro link abre a pergunta "Should I activate it now?".
- Servidor Mac do GitHub (macOS 27): o `kickstart` do compartilhamento de tela trava, então não dá para
  o usuário usar o Mac remoto. A gravação `screencapture -V` sai sem as janelas de imagem do IsiX; o
  vídeo do teste é feito de uma captura por segundo. A tela tem 1024 x 768.
- Arquivo vazio derruba `gh release upload` de todos os arquivos; artefatos do GitHub não chegam a esta
  sessão (`republicar.yml` os copia para uma versão de teste).
- Botão do PACS sem hospital: `engine/scripts/fake_pacs.py` é um PACS de teste (C-FIND com número
  de imagens, C-MOVE); `isix.yml` o usa com um link no formato do hospital.
- O matplotlib desta sessão usa a fonte Inter por configuração local; as páginas fixam DejaVu Sans
  para saírem iguais em qualquer máquina.
