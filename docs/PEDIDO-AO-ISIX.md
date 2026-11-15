# Pedido ao autor do IsiX DICOM Viewer

Texto pronto para você enviar em
<https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/issues/new>.
Eu não consigo abrir pedidos em repositórios de outras pessoas a partir desta
sessão. O autor publica versões quase todo dia; se ele atender, o botão do PACS
passa a funcionar sem depender do nosso complemento.

Pode colar como está. Não há dado de paciente nem nome de servidor no texto.

---

**Título:** Links `osirix://` do OsiriX MD: `then=Open`, `retrieveOnlyIfNeeded` e parâmetros com maiúsculas

Olá, Thales. Obrigado pelo IsiX.

O botão "abrir no OsiriX" do PACS do meu hospital gera este link (valores trocados por XXX):

```
osirix://?methodName=Retrieve&retrieveOnlyIfNeeded=yes&ServerName=XXX&filterKey=StudyInstanceUID&filterValue=XXX&then=Open
```

No OsiriX MD ele busca o exame no servidor e o abre. Lendo o código da versão 6.0.3
(`Horos/Sources/XMLRPCInterface+Retrieve.swift` e `HorosSchemeURL.swift`), o IsiX
aceita o `Retrieve` por `StudyInstanceUID`, mas:

1. **`then=Open` é ignorado.** O exame chega ao banco e não abre.
2. **`retrieveOnlyIfNeeded=yes` é ignorado.** O exame é buscado de novo mesmo quando já está no banco.
3. **Os nomes dos parâmetros diferenciam maiúsculas.** `Retrieve` lê `serverName`; um link
   com `ServerName` é recusado com "server name is empty".

Seria possível dar suporte a esses três pontos, para que links escritos para o
OsiriX MD funcionem sem alteração?

**Um segundo ponto, de segurança.** O README diz que, por padrão, o servidor XML-RPC
atende só este Mac. Em uma instalação nova da 6.0.3 (macOS 27), ao ligar o suporte a
URL, o registro mostrou:

```
--- XML-RPC interface activated on port: 8080 (HTTP), answering this Mac and any address, WITHOUT a password
```

O valor registrado de `httpXMLRPCServerAccessScope` em `NetworkPreferences.swift` é `2`
(qualquer endereço). Como `FindObject` devolve nomes e identificadores de pacientes,
talvez o padrão devesse ser `0` (só este Mac), como o README descreve.
