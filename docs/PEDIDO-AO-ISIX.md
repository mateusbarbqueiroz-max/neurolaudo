# Pedido ao autor do IsiX DICOM Viewer

Situação em 16/11/2026: **ainda não enviado.** A sessão do Claude não consegue
abrir pedidos no repositório do autor (só age em repositórios onde o usuário
pode gravar). O envio fica com o usuário.

## Como enviar

1. Abra <https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/issues/new>,
   já conectado à sua conta do GitHub.
2. Cole o título e o texto abaixo. Estão em inglês, que é a língua do repositório.
3. Clique em **Create** (ou **Submit new issue**).
4. Me passe o endereço do pedido criado, para eu acompanhar a resposta.

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
