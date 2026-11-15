# Pendências

Atualizado em 15/11/2026.

## Situação do Mac

O Mac atual do usuário é antigo demais para o IsiX (que exige macOS 15 ou mais
novo). O Mac novo, onde a esposa dele vai trabalhar, chega por volta de
**4 de janeiro de 2027**. Antes disso, ele vai tentar o computador de um amigo.

Até lá, o único Mac disponível é o servidor do GitHub, onde o complemento é
compilado e, se possível, aberto dentro do IsiX com o exame de teste.

## Do usuário

| Pendência | Quando | Importância |
| --- | --- | --- |
| Instalar o IsiX e testar o botão do PACS, seguindo `docs/GUIA-INSTALACAO.md` | Quando houver um Mac com macOS 15+ (amigo ou Mac novo) | Alta: é o teste da Etapa 1 |
| Instalar o complemento (Passo 6 do guia) e dizer o que apareceu | Junto com o item acima | Alta |
| Enviar o formato do link do botão do PACS, com os valores trocados por `XXX` | Só se o botão não funcionar no IsiX | Baixa: o IsiX aceita todos os comandos de link do OsiriX |
| Enviar os nomes das séries dos exames de rotina (RM de encéfalo e TC de crânio) | Quando puder; dá para ver no OsiriX MD atual | Média: ajusta os protocolos de exibição ao serviço |
| Conferir os valores das janelas de TC (encéfalo 40/80, AVC 40/40, subdural 75/215, osso 600/2800, angio-TC 200/700, partes moles 50/350) | Quando puder | Média |
| Instalar o FreeSurfer 8.2 no Mac novo (registro gratuito) | Quando a volumetria estiver pronta para teste | Só para a Etapa 3 |

## Do Claude

| Pendência | Depende de |
| --- | --- |
| Complemento compilando no servidor Mac e publicado | nada |
| Teste automático: IsiX + complemento + exame de teste no servidor Mac, com captura de tela | o IsiX abrir no servidor |
| Testar `mac/botao-pacs.sh` e `mac/instalar.sh` no servidor Mac | nada |
| Protocolos de exibição nativos do IsiX configurados para neuro | nomes das séries |
| Volumetria: seleção da série, chamada ao FreeSurfer, relatório, saída DICOM | nada para escrever; Mac para testar |
| Laudo | etapas anteriores |
