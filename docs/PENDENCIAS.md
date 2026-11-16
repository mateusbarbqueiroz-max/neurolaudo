# Pendências

Atualizado em 16/11/2026.

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
| Avisar o Claude quando o autor do IsiX responder ao pedido [ThalesMMS/IsiX-DICOM-Viewer-macOS#48](https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/issues/48), enviado em 16/11/2026 | Quando chegar o e-mail do GitHub | Alta: resolve na origem o `then=Open` e o `ServerName` |
| Quando o autor indicar um contato, enviar em particular o aviso sobre a porta de comandos (o Claude entrega o texto) | Depois da resposta do autor | Alta: é um ponto de segurança, não vai em pedido público |
| Instalar o IsiX e o complemento e testar o botão do PACS, seguindo `docs/GUIA-INSTALACAO.md` | Quando houver um Mac com macOS 15+ (amigo ou Mac novo) | Alta: é o teste da Etapa 1 |
| Usar as medidas em um exame real, desenhando as linhas à mão (Evans, linha média, ABC/2), e abrir o painel do ASPECTS | Junto com o item acima | Média: o cálculo já foi conferido dentro do IsiX com marcas desenhadas pelo complemento; faltam o uso à mão e as telas |
| Enviar os nomes das séries dos exames de rotina (RM de encéfalo e TC de crânio) | Quando puder; dá para ver no OsiriX MD atual | Média: ajusta os protocolos de exibição ao serviço |
| Conferir os valores das janelas de TC (encéfalo 40/80, AVC 40/40, subdural 75/215, osso 600/2800, angio-TC 200/700, partes moles 50/350) | Quando puder | Média |
| Ver os exemplos da volumetria (`docs/exemplo-volumetria.png`, `docs/exemplo-conferencia.png`, `docs/volumetria-no-isix.png`) e dizer o que mudar: estruturas, ordem, cores, palavras, frase para o laudo | Quando puder; não precisa de Mac | Média: é a hora mais barata de mudar |
| Instalar o motor de volumetria (Passo 8 do guia) e rodar em um T1 volumétrico; conferir o mapa colorido e contar o tempo que levou | Quando houver o Mac novo | Alta para a volumetria: é o primeiro teste em exame real |
| Se houver laudos do NeuroQuant de exames antigos, rodar a nossa volumetria nos mesmos exames e comparar | Depois do item acima | Média: mostra o quanto os dois métodos diferem |

## Do Claude

| Pendência | Depende de |
| --- | --- |
| Encaminhador de links, se o link usar `ServerName` e o autor do IsiX não atender | resposta do usuário e do autor |
| Protocolos de exibição nativos do IsiX configurados para neuro | nomes das séries |
| Volumetria em exame real: ajustar o que o primeiro teste no Mac mostrar (tempo, memória, nomes de série) | teste do usuário no Mac novo |
| Volumetria: ver se as notas automáticas de qualidade cabem na memória do Mac novo e, se couberem, oferecê-las como conferência extra | Mac novo |
| Volumetria: comparação com o exame anterior do mesmo paciente (mudança de volume no tempo) | opinião do usuário sobre o relatório |
| Laudo | etapas anteriores |

## Feito

- Volumetria (16/11/2026; números em `docs/VOLUMETRIA.md`):
  - o motor reproduz a referência nas estruturas grandes e tem ruído de 1 a 3 %, sem desvio, nas
    pequenas, em 8 voluntários públicos;
  - a mesma imagem dá volumes idênticos em Linux e em Mac com Apple Silicon (recorte de 12 cm);
  - o instalador funciona em Mac sem compilador;
  - o comando roda do começo ao fim dentro do IsiX com o exame de teste, e o mapa colorido abre ao
    lado do T1, no mesmo corte.

- Código no GitHub; testes em Linux e compilação em Mac a cada envio.
- Complemento carregado pelo IsiX 6.0.3 no servidor Mac, com os 14 comandos no menu.
- Abertura automática do exame que chega e janela de osso por ⌃⌥4, vistas em captura de tela.
- `mac/instalar.sh` e `mac/botao-pacs.sh` executados em macOS 27.
- Medidas conferidas dentro do IsiX pelo autoteste do complemento: 5 de 5, com o
  comprimento igual ao que o próprio IsiX mede.
- Protocolo de RM (seis séries na ordem) e comparação com exame anterior,
  exercitados no IsiX com exames de teste e vistos em captura de tela.
