# Pedido ao autor do IsiX DICOM Viewer

Situação: **atendido**. Enviado pelo usuário em 16/11/2026, como
[ThalesMMS/IsiX-DICOM-Viewer-macOS#48](https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/issues/48).
O autor respondeu em 18/11 ("Working on it now") e em 19/11 ("Please update to
the latest version"). O que mudou, conferido no código da 6.0.6:

- 6.0.4: os nomes dos parâmetros valem em qualquer caixa (`ServerName` funciona);
  `retrieveOnlyIfNeeded=yes` não busca um exame que já está completo no Mac;
  `then=open` (ou `display`) abre o exame assim que chega a primeira série.
- 6.0.5: o esquema `isix://`; o IsiX avisa ao abrir quando outro programa abre os
  links `osirix://` e oferece tomá-los de volta; a espera do `then=open` vira um
  ajuste oculto (`XMLRPCRetrieveOpenWaitSeconds`, 30 s).
- Detalhes em `docs/FATOS-ISIX.md`, seção do link do botão do PACS.

Sobre a observação de segurança, o autor pediu que vá pelo canal privado do
GitHub (aba Security do repositório dele, "Report a vulnerability"), ou por
e-mail ou LinkedIn do perfil dele. O texto foi entregue ao usuário na conversa
e não fica neste repositório público, por ser um aviso privado.

A sessão do Claude não consegue abrir nem comentar pedidos no repositório do
autor, nem ler os comentários pela API do GitHub; lê a página pública.

Não há dado de paciente nem nome de servidor no texto.

## Título

```
osirix:// links written for OsiriX MD: then=Open, retrieveOnlyIfNeeded and parameter name case
```

## Texto

````
Hello, and thank you for IsiX.

The "open in OsiriX" button of my hospital's PACS generates this link (values replaced by XXX):

```
osirix://?methodName=Retrieve&retrieveOnlyIfNeeded=yes&ServerName=XXX&filterKey=StudyInstanceUID&filterValue=XXX&then=Open
```

In OsiriX MD it retrieves the study from the DICOM node and opens it. Reading the 6.0.3 source (`Horos/Sources/XMLRPCInterface+Retrieve.swift`, `Horos/Sources/HorosSchemeURL.swift`), IsiX accepts `Retrieve` by `StudyInstanceUID`, but:

1. `then=Open` is ignored: the study arrives in the database and is not opened.
2. `retrieveOnlyIfNeeded=yes` is ignored: the study is retrieved again even when it is already in the database.
3. Parameter names are case-sensitive: `Retrieve` reads `serverName`, so a link with `ServerName` would fail with "server name is empty". I am still confirming the exact spelling my PACS uses.

Would you consider supporting these, so that links written for OsiriX MD work unchanged?

I have not tested this against the hospital PACS yet (no compatible Mac at hand); the above comes from reading the code. I am happy to test a build when I can.

Separately, I have a security-related observation about the XML-RPC defaults that I would rather share privately. Is there a contact you prefer for that?

This report was prepared with the help of an AI assistant (Claude).
````

## O ponto de segurança

A observação sobre a porta de comandos (`docs/FATOS-ISIX.md`, seção "Porta de
comandos") não vai no pedido público: o costume é avisar o autor em particular.
O repositório dele não tem canal de aviso privado nem política de segurança,
por isso o pedido acima pergunta por um contato. Quando ele responder, o Claude
entrega o texto do aviso para envio.

Enquanto isso, o guia de instalação já traz o ajuste que protege o seu Mac
(Passo 5: atender só este Mac).
