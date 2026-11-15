# NeuroLaudo

Ferramentas de neurorradiologia sobre o IsiX DICOM Viewer, derivado aberto do
Horos/OsiriX. Plano aprovado em `docs/PLANO.md`.

## Quem usa e como falar

- O usuário é neurorradiologista e não programa. Fala português do Brasil.
  Explique sem jargão de programação; termos médicos estão liberados.
- Ele testa no Mac dele (Apple Silicon, 16 GB+) e relata o que viu. Não tem
  Xcode: o trabalho é só pela nuvem, com compilação nos servidores Mac do GitHub.
- Para diagnóstico ele usa o OsiriX MD, que é certificado. O IsiX e o NeuroLaudo
  são apoio, sem certificação.

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
- `engine/`: motor em Python (leitura DICOM; volumetria por fazer).
- `mac/`: scripts para o Mac do usuário.

## Comandos

- Testes do complemento em Linux: `cd plugin && swift test`.
- Testes do motor: `cd engine && python -m pytest -q`.
- Compilar o complemento: só em macOS, `plugin/script/build.sh --configuration Release`.

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
