# Pendências

Atualizado em 21/11/2026.

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
| Instalar o IsiX e o complemento e testar o botão do PACS, seguindo `docs/GUIA-INSTALACAO.md` (IsiX 6.0.7 ou mais novo). Se o IsiX disser que o pedido não foi enviado, conferir no link se está escrito `StudyInstanceUID` (na transcrição de 15/11 veio `StudyInstancrUID`) | Quando houver um Mac com macOS 15+ (amigo ou Mac novo) | Alta: é o teste da Etapa 1 |
| Usar as medidas em um exame real, desenhando as linhas à mão (Evans, linha média, ABC/2), e abrir o painel do ASPECTS | Junto com o item acima | Média: o cálculo já foi conferido dentro do IsiX com marcas desenhadas pelo complemento; faltam o uso à mão e as telas |
| Mandar ao Claude os nomes das séries do serviço: com os exames reais já no IsiX, abrir **Plugins > Database > Nomes das séries (para ensinar o NeuroLaudo)**, tocar em **Copiar** e colar na conversa. Junto, dizer como gosta de ver a RM de encéfalo e a TC de crânio na tela (quantas janelas e qual série em cada) | Quando o Mac novo chegar e os primeiros exames tiverem passado pelo botão do PACS. Dá para adiantar pelo OsiriX MD, com a página explicativa entregue na conversa de 20/11/2026 | Média: com isso o IsiX passa a abrir o exame do botão já arrumado para neuro, e os nomes não reconhecidos são ensinados ao NeuroLaudo |
| Mandar 2 ou 3 máscaras de laudo que usa no Laudite (RM de crânio, TC de crânio), sem dados de paciente | Quando puder; não precisa de Mac | Alta para a etapa do laudo |
| Conferir os valores das janelas de TC (encéfalo 40/80, AVC 40/40, subdural 75/215, osso 600/2800, angio-TC 200/700, partes moles 50/350) | Quando puder | Média |
| Ver os exemplos da volumetria (`docs/exemplo-volumetria.png`, `docs/exemplo-conferencia.png`, `docs/volumetria-no-isix.png`, `docs/exemplo-comparacao.png`) e dizer o que mudar: estruturas, ordem, cores, palavras, frase para o laudo | Quando puder; não precisa de Mac | Média: é a hora mais barata de mudar |
| Instalar o motor de volumetria (Passo 8 do guia) e rodar em um T1 volumétrico; conferir o mapa colorido e contar o tempo que levou | Quando houver o Mac novo | Alta para a volumetria: é o primeiro teste em exame real |
| Se houver laudos do NeuroQuant de exames antigos, rodar a nossa volumetria nos mesmos exames e comparar | Depois do item acima | Média: mostra o quanto os dois métodos diferem |
| Em um paciente com dois exames com T1 3D (controle de demência, por exemplo), rodar a volumetria no exame antigo e depois no novo, e ver a página de comparação (Passo 8 do guia) | Depois dos dois itens acima | Média: é o primeiro teste da comparação em exame real |

## Do Claude

| Pendência | Depende de |
| --- | --- |
| Com a lista do comando Nomes das séries: ensinar ao NeuroLaudo os nomes "não reconhecidos" e configurar os protocolos de exibição do IsiX para neuro | a lista colada pelo usuário |
| Volumetria em exame real: ajustar o que o primeiro teste no Mac mostrar (tempo, memória, nomes de série) | teste do usuário no Mac novo |
| Volumetria: ver se as notas automáticas de qualidade cabem na memória do Mac novo e, se couberem, oferecê-las como conferência extra | Mac novo |
| Volumetria: ajustar a página de comparação com o exame anterior (palavras, estruturas, limites) | opinião do usuário e primeiro uso em exame real |
| Volumetria: medir o limite de repetição em idosos e em 1,5 T, se aparecer um banco público com exames repetidos nessas condições | dados públicos |
| Laudo: o usuário dita no Laudite, com máscaras e frases prontas. O NeuroLaudo entrega o texto das medidas e da volumetria no formato das máscaras dele, pronto para colar | máscaras do usuário |
| Lesões de substância branca no FLAIR: o estudo (`docs/LESOES-FLAIR.md`) mostrou que roda num Mac de 16 GB com a versão por fatias. A repetição em 164 exames públicos deu ±2,3 mL no mesmo aparelho e ±4,6 mL entre aparelhos, com mediana de 7,3 mL em voluntários saudáveis. Falta a decisão do usuário sobre a utilidade | opinião do usuário |

## Feito

- Estudo das lesões no FLAIR (21/11/2026, `docs/LESOES-FLAIR.md`): a versão por fatias roda em cerca de
  6 GB e dá o mesmo resultado do WMH-SynthSeg original, conferido num exame inteiro (mesmo rótulo em
  100 % dos voxels). Repetição medida em 164 exames públicos. Não faz parte do complemento.
- Volumetria comparada com o exame anterior do mesmo paciente (21/11/2026): página nova no relatório,
  com a variação, a taxa por ano e o limite de repetição medido em 20 voluntários públicos escaneados
  em vários aparelhos (`docs/VOLUMETRIA.md`). Conferida em Linux e dentro do IsiX 6.0.7 no servidor
  Mac, com o fantoma e um exame anterior dele no histórico: relatório com 3 páginas, frase da
  comparação no resumo, e a janela de texto longo com barra de rolagem funcionando.
- Teste dentro do IsiX roda sozinho toda segunda-feira, com a versão mais nova do IsiX.

- Aviso de segurança sobre a porta de comandos enviado pelo usuário ao autor do IsiX, por e-mail, em 20/11/2026.
- IsiX 6.0.7 (20/11/2026) adotou as duas sugestões do aviso: links sem porta de rede, com opção própria, e porta de comandos atendendo só o próprio Mac de fábrica. Guia ajustado.

- Pedido ao autor do IsiX atendido (18 e 19/11/2026): desde a 6.0.4 o link do botão do PACS
  funciona como está escrito (`ServerName`, `retrieveOnlyIfNeeded`, `then=Open`). O
  encaminhador de links deixou de ser necessário. Detalhes em `docs/PEDIDO-AO-ISIX.md`.
- Botão do PACS simulado no servidor Mac com o IsiX 6.0.6 (20/11/2026): com um PACS de teste e um
  link no formato do hospital, o IsiX buscou o exame, abriu-o sozinho e não buscou de novo no
  segundo clique; o complemento não abriu janelas a mais (`docs/FATOS-ISIX.md`).

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
