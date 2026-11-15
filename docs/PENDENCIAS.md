# Pendências

Atualizado em 15/11/2026.

## Situação do Mac

O Mac atual do usuário é antigo demais para o IsiX (que exige macOS 15 ou mais
novo). O Mac novo, onde a esposa dele vai trabalhar, chega por volta de
**4 de janeiro de 2027**. Antes disso, ele vai tentar o computador de um amigo.

Até lá, o único Mac disponível é o servidor do GitHub. Nele o complemento já é
compilado, instalado e exercitado dentro do IsiX (`docs/FATOS-ISIX.md`, seção
"Conferido no servidor Mac").

## Do usuário

| Pendência | Quando | Importância |
| --- | --- | --- |
| Conferir se o link do botão do PACS traz `ServerName` ou `serverName` | Quando puder ver o código da página do PACS | Alta: com S maiúsculo o IsiX recusa o pedido |
| Enviar ao autor do IsiX o texto de `docs/PEDIDO-AO-ISIX.md` | Quando puder | Alta: resolve na origem o `then=Open`, o `ServerName` e a porta de comandos aberta |
| Instalar o IsiX e o complemento e testar o botão do PACS, seguindo `docs/GUIA-INSTALACAO.md` | Quando houver um Mac com macOS 15+ (amigo ou Mac novo) | Alta: é o teste da Etapa 1 |
| Testar as medidas desenhando linhas em um exame (Evans, linha média, ABC/2) e o painel do ASPECTS | Junto com o item acima | Alta: só foram testadas fora do IsiX |
| Enviar os nomes das séries dos exames de rotina (RM de encéfalo e TC de crânio) | Quando puder; dá para ver no OsiriX MD atual | Média: ajusta os protocolos de exibição ao serviço |
| Conferir os valores das janelas de TC (encéfalo 40/80, AVC 40/40, subdural 75/215, osso 600/2800, angio-TC 200/700, partes moles 50/350) | Quando puder | Média |
| Instalar o FreeSurfer 8.2 no Mac novo (registro gratuito) | Quando a volumetria estiver pronta para teste | Só para a Etapa 3 |

## Do Claude

| Pendência | Depende de |
| --- | --- |
| Encaminhador de links, se o link usar `ServerName` e o autor do IsiX não atender | resposta do usuário e do autor |
| Protocolos de exibição nativos do IsiX configurados para neuro | nomes das séries |
| Exercitar no servidor Mac o protocolo de RM e a comparação com anterior (exame de teste de RM com dois estudos) | nada |
| Volumetria: seleção da série, chamada ao FreeSurfer, relatório, saída DICOM | nada para escrever; Mac para testar |
| Laudo | etapas anteriores |

## Feito

- Código no GitHub; testes em Linux e compilação em Mac a cada envio.
- Complemento carregado pelo IsiX 6.0.3 no servidor Mac, com os 14 comandos no menu.
- Abertura automática do exame que chega e janela de osso por ⌃⌥4, vistas em captura de tela.
- `mac/instalar.sh` e `mac/botao-pacs.sh` executados em macOS 27.
