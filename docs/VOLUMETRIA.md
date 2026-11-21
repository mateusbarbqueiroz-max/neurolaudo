# Volumetria cerebral

**Uso em pesquisa. Não validada para diagnóstico.** É apoio à leitura, como o
restante do NeuroLaudo. Os percentis não equivalem aos do NeuroQuant.

## O que ela entrega

A partir de um T1 volumétrico (3D) sem contraste:

- volume de dez estruturas: hipocampos, amígdalas e tálamos de cada lado,
  ventrículos laterais, córtex cerebral, substância branca cerebral e encéfalo
  (parênquima), além do volume intracraniano total;
- o percentil de cada volume para a idade e o sexo, com o volume ajustado ao
  tamanho da cabeça;
- a assimetria dos hipocampos;
- um relatório de uma página (tabela e gráficos), uma página de conferência com
  cortes coloridos e uma série colorida, corte a corte, para conferir a
  segmentação ao lado do T1;
- uma frase pronta para colar no laudo, já com a ressalva de uso em pesquisa;
- se o mesmo paciente já teve a volumetria feita neste Mac em um exame mais
  antigo, uma página de comparação com ele (seção abaixo).

Exemplos, com voluntários de banco público (não são pacientes):

- `docs/exemplo-volumetria.png`: o relatório (voluntário IXI072);
- `docs/exemplo-conferencia.png`: a página de conferência, com segmentação de
  verdade (voluntário IXI002);
- `docs/volumetria-no-isix.png`: o resultado dentro do IsiX, com o exame de
  teste (fantoma): o T1 à esquerda e o mapa colorido à direita, no mesmo corte;
- `docs/exemplo-comparacao.png`: a página de comparação com o exame anterior,
  em um exemplo fictício (volumes de voluntário público alterados de propósito).

## Como funciona

1. **No IsiX**, o comando *Plugins > Image Filters > Volumetria cerebral
   (pesquisa)…* copia os cortes da série aberta para um arquivo de volume. A
   posição e a orientação de cada corte vêm do próprio exame.
2. **O motor** (programa em Python instalado à parte, `mac/instalar-volumetria.sh`):
   - acha a cabeça na imagem e recorta em volta dela;
   - segmenta com o SynthSeg 2.0 em modo rápido, no processador;
   - recorta de novo, agora pelo que foi segmentado mais 15 mm (a mesma caixa
     usada para construir a referência), e segmenta outra vez;
   - compara cada volume com a referência por idade e sexo.
3. **De volta ao IsiX**, o complemento grava no exame duas séries novas (o
   relatório e o mapa colorido), abre o mapa no mesmo corte em que o T1 está e
   mostra o resumo.

A imagem não sai do Mac. A pasta temporária, com a imagem e o nome do paciente,
é apagada no fim, dê certo ou não.

## Comparação com o exame anterior

Quando o mesmo paciente já teve a volumetria feita **neste Mac** em um exame
mais antigo, o relatório ganha uma página entre a principal e a de conferência:

- o volume de cada estrutura nos dois exames, a variação e a taxa por ano (só
  com intervalo de 6 meses ou mais);
- o **limite de repetição**: a maior variação que só repetir o exame produz em
  95 % das vezes. Só é marcado (▼ redução, ▲ aumento) o que passa desse limite;
- a trajetória de cada estrutura sobre as faixas da referência, na idade de
  cada exame;
- uma frase a mais na frase para o laudo.

**Qual limite.** Se o tamanho do voxel, o TR e o TE são iguais nos dois exames,
vale o limite do mesmo aparelho; se mudam, ou se faltam, o de aparelhos
diferentes, que é maior. A variação usa o volume ajustado ao volume
intracraniano de cada exame (o mesmo dos percentis): entre aparelhos ele variou
menos que o volume bruto.

**Como o exame anterior é achado.** Pelo número do paciente, no histórico deste
Mac. Se o exame anterior ainda não foi medido aqui, rode a volumetria primeiro
no T1 dele e depois no atual. Exames com o mesmo número, mas com idade ou sexo
que não fecham com o atual, ficam de fora, com aviso.

**O histórico.** Fica só neste Mac, em `~/Library/Application
Support/NeuroLaudo/historico`. De cada exame guarda os volumes, o volume
intracraniano, a data, a idade, o sexo, o nome da série, o tamanho do voxel, o TR
e o TE. O nome do paciente não é gravado; o número do paciente e o do exame viram
um código (HMAC-SHA-256 com uma chave aleatória criada neste Mac) que só serve
para reconhecer de novo o mesmo paciente. Apagar a pasta apaga o histórico.

### Limite de repetição medido (21/11/2026)

Banco público ON-Harmony (OpenNeuro ds004712, CC0; Warrington e colaboradores,
Scientific Data, 2025): 20 adultos saudáveis de 19 a 50 anos, cada um escaneado
em 6 aparelhos de 3 T (Siemens, Philips e GE), e 9 deles mais 5 vezes no mesmo
aparelho, em dias diferentes. Foram 165 exames, com a volumetria completa em
cada um (a mesma do complemento), nos servidores Linux do GitHub; em média um
minuto por exame.

| Estrutura | Mesmo aparelho | Aparelhos diferentes |
| --- | --- | --- |
| Hipocampo esquerdo | ±2,5 % | ±3,6 % |
| Hipocampo direito | ±2,8 % | ±4,1 % |
| Amígdala esquerda | ±7,5 % | ±8,8 % |
| Amígdala direita | ±8,5 % | ±8,5 % |
| Tálamo esquerdo | ±3,6 % | ±5,5 % |
| Tálamo direito | ±4,4 % | ±7,8 % |
| Ventrículos laterais | ±4,0 % | ±6,4 % |
| Córtex cerebral | ±0,9 % | ±2,5 % |
| Substância branca cerebral | ±0,8 % | ±2,0 % |
| Encéfalo (parênquima) | ±0,7 % | ±1,2 % |

Conferência: no mesmo aparelho, 4 a 7 % dos pares de exames da mesma pessoa
passaram do limite (o esperado é 5 %); entre aparelhos, 4 a 7 %.

Como ler:

- **Hipocampos**: o limite fica em 2,5 a 4 %. Para ter a escala, a perda anual
  do hipocampo na literatura é de cerca de 1,4 % em idosos saudáveis e de 4,7 %
  na doença de Alzheimer (metanálise de Barnes e colaboradores, 2009). Em
  intervalos curtos, a comparação só deve marcar perdas grandes.
- **Amígdalas**: limite de 7,5 a 8,8 %. Pouco úteis para acompanhar.
- **Encéfalo, córtex e substância branca**: os mais estáveis.
- **Aparelho puxa para um lado**: em um dos aparelhos (GE), o tálamo direito
  saiu em média 5,5 % menor que nos outros; nas demais estruturas, a diferença
  média de cada aparelho ficou em até 2 %. Por isso o limite entre aparelhos é
  maior.

Arquivos completos: `repeticao.txt`, `repeticao.json` e `repeticao-exames.csv` na
versão `teste-volumetria` do repositório. O motor usa
`engine/neurolaudo/volumetry/data/repeticao.json`.

## De onde vêm os programas e a referência

| Peça | Origem | Licença |
| --- | --- | --- |
| `mri_synthseg` | FreeSurfer 8.2.0, baixado do repositório oficial e conferido por soma SHA-256 | licença do FreeSurfer; SynthSeg, Apache 2.0 |
| Modelos treinados do SynthSeg 2.0 | servidor oficial do FreeSurfer, conferidos por soma SHA-256 | idem |
| Biblioteca `surfa` 0.6.3 | FreeSurfer; compilada pelo projeto para Mac, porque só existe em código-fonte | MIT |
| Referência (normas) | Neurodesk, `recipes/synthseg/brainquant_norms.json`: 561 adultos saudáveis do banco IXI, de 20 a 86 anos | MIT; dados do IXI, CC BY-SA 3.0 |

Não é a instalação completa do FreeSurfer (20 GB): o instalador baixa só essas
peças, cerca de 2 GB com o Python e as bibliotecas.

## O que foi conferido (16/11/2026)

Tudo em servidores do GitHub, com exames públicos ou com o exame de teste.
Nenhum exame de paciente.

| O quê | Onde | Resultado |
| --- | --- | --- |
| Cálculo dos percentis | Linux, os 561 voluntários da tabela pública | de 88,8 % a 91,3 % dos voluntários entre os percentis 5 e 95, como esperado |
| Segmentação de verdade, com o recorte original da referência (SynthStrip) | Linux, 8 voluntários, dois hospitais | volumes idênticos aos publicados: 0,00 % em todas as estruturas |
| Segmentação de verdade, com o recorte que o motor usa hoje (dois passos) | Linux, os mesmos 8 voluntários | tabela abaixo; de 1,5 a 2,5 minutos e cerca de 7 GB por exame, conforme o servidor |
| Mesma imagem em Linux e em Mac com Apple Silicon | recorte de 12 cm de um exame público, três rodadas | volumes idênticos (0,00 %); no Mac, 17 a 34 s e 2,8 GB |
| Instalador | Linux; Mac com Apple Silicon (macOS 27) com o compilador bloqueado, como no Mac sem Xcode | instala, e as bibliotecas carregam |
| Comando do complemento dentro do IsiX 6.0.3 | servidor Mac, exame de teste | copia a série, chama o motor, grava relatório (2 imagens) e mapa (96 imagens) no exame, abre o mapa no mesmo corte do T1 e mostra o resumo |
| Volume gravado pelo complemento | Linux, a cada envio | o motor lê a mesma forma, voxel, orientação e valores |

No teste dentro do IsiX só a segmentação era uma imitação (rótulos por
limiar); o restante do motor era o de verdade.

### Diferença em relação aos volumes publicados, com o recorte atual

Diferença, em %, entre o volume medido pelo motor e o publicado pelo Neurodesk
para o mesmo exame, nos 8 voluntários. A última coluna põe o desvio em
perspectiva: quanto ele representa da variação entre pessoas saudáveis da
mesma idade (o "desvio-padrão" da referência).

| Estrutura | Média | Desvio | Maior | Desvio, em desvios-padrão da referência |
| --- | --- | --- | --- | --- |
| Hipocampo esquerdo | −0,34 | 1,13 | 2,27 | 0,15 |
| Hipocampo direito | +0,05 | 1,20 | 2,27 | 0,16 |
| Amígdala esquerda | −0,63 | 3,16 | 6,02 | 0,42 |
| Amígdala direita | −0,79 | 2,07 | 3,99 | 0,28 |
| Tálamo esquerdo | +0,40 | 1,20 | 1,88 | 0,18 |
| Tálamo direito | −0,33 | 2,24 | 4,08 | 0,36 |
| Ventrículos laterais | −0,03 | 0,76 | 1,65 | 0,02 |
| Córtex cerebral | +0,02 | 0,06 | 0,12 | 0,02 |
| Substância branca cerebral | 0,00 | 0,14 | 0,19 | 0,04 |
| Encéfalo (parênquima) | −0,03 | 0,07 | 0,14 | 0,04 |
| Volume intracraniano | −0,03 | 0,12 | 0,28 | — |

Em sete dos oito exames o motor fez as duas segmentações. No oitavo, a caixa
da cabeça já estava a menos de 6 mm da caixa final, e ele parou na primeira.

Leitura: nas estruturas grandes o motor reproduz a referência. Nas pequenas
(hipocampo, amígdala, tálamo) há um ruído de 1 a 3 %, sem desvio para um lado:
com oito exames, nenhuma média se afasta de zero mais do que o acaso explica.
Esse ruído vem do próprio SynthSeg, que dá um resultado um pouco diferente
conforme o enquadramento da imagem; ele existe também entre dois exames da
mesma pessoa. Na prática, um percentil de hipocampo perto do limite (por
exemplo, 4 ou 6) deve ser lido como limítrofe.

## O que falta conferir

- **Exame inteiro em Mac.** O servidor Mac do GitHub tem 7 GB de memória e o
  exame inteiro não cabe nele. Em Linux o motor usou cerca de 7 GB; o Mac novo, com
  16 GB ou mais, deve dar conta, mas tempo e memória só serão medidos nele.
- **Exames reais.** Nomes de série do hospital, aparelhos, exames com contraste
  e anatomia alterada. Tudo o que foi medido até aqui é de voluntários
  saudáveis de um banco público.
- **Comparação com o NeuroQuant**, se houver laudos dele dos mesmos exames.
- **Comparação entre exames em pacientes.** O limite de repetição foi medido em
  adultos jovens e saudáveis, em 3 T e com voxel de 1 mm. Em idosos (mais
  movimento, mais atrofia), em 1,5 T e com voxels maiores a variação deve ser
  maior, e isso não foi medido. A página de comparação também ainda não foi vista
  dentro do IsiX com exames reais.

## Decisões e porquês

- **Mesmos passos da referência, até onde o Mac permite.** Um percentil só vale
  se o volume do paciente for medido do mesmo jeito que os volumes da
  referência. A referência recortou cada imagem em volta do encéfalo com o
  programa SynthStrip. Ele não roda em Mac com Apple Silicon em tempo razoável
  (no servidor de teste não terminou em 20 minutos nem com imagem pequena),
  porque ali o PyTorch faz as contas em 3D por um caminho que pede dezenas de
  GB. O motor chega à mesma caixa por outro caminho: acha a cabeça pelo
  contorno, segmenta, e recorta de novo pelo que foi segmentado mais 15 mm.
- **Dois passos, e não um.** Com um passo só (recorte pela cabeça), a amígdala
  direita saiu em média 2,4 % menor e o hipocampo direito 1,0 % menor que na
  referência. Com o segundo passo esses desvios somem. Custa o dobro do tempo.
- **Sem as notas automáticas de qualidade do SynthSeg.** Com elas (`--qc`) os
  volumes mudam (até 1,3 % no córtex) e a memória necessária estoura. Ficam
  como opção (`--qualidade`), desligada. A conferência de qualidade é a do
  olho: a página e a série coloridas.
- **Cores diferentes para cada lado** em hipocampo, amígdala e tálamo, e letras
  D e E nas imagens: uma troca de lado tem de aparecer na imagem.
- **Trava de orientação.** O complemento calcula a orientação do volume que
  gravou, e o motor informa a que leu do arquivo. Se as duas não baterem, nada
  é gravado no exame.
- **Aviso de borda.** Se, no fim, o encéfalo segmentado encostar na borda da
  imagem, o relatório avisa que parte dele pode ter ficado fora do campo de
  visão.
- **Recusas.** O comando não roda em TC, em série com menos de 60 cortes, em
  série com cortes faltando ou repetidos, nem em FLAIR, difusão e afins. Avisa
  quando o nome da série sugere contraste ou não é reconhecido como T1.

## Limites do método

- A referência cobre adultos de 20 a 86 anos. Fora disso o relatório avisa que
  os percentis são extrapolados. Não serve para crianças.
- Entre aparelhos diferentes o resultado pode deslocar até cerca de 0,5
  desvio-padrão (estimativa do Neurodesk).
- Nas estruturas pequenas, o enquadramento da imagem muda o volume em 1 a 3 %
  (tabela acima).
- A página principal é medida de um único momento. A variação no tempo está
  na página de comparação, quando há exame anterior medido neste Mac; o limite
  de repetição dela vale para adultos jovens em 3 T (seção acima).
- A referência é de T1 sem contraste, com voxel de cerca de 1 mm. Acima de
  1,5 mm o relatório avisa.
- A segmentação pode errar em anatomia muito alterada (grandes lesões, cirurgia,
  hidrocefalia acentuada). Por isso a conferência visual é parte do uso.

## Como repetir as medições

No GitHub, aba Actions, fluxo "Volumetria (teste real)", opção `onde`:
`linux` (8 voluntários), `miniatura` (o recorte em Linux e Mac),
`diagnostico` (tempo e memória por configuração) ou `repeticao` (limite de
repetição: 20 voluntários do ON-Harmony, um servidor por pessoa, cerca de 15
minutos). Depois de `repeticao`, copiar o `repeticao.json` publicado para
`engine/neurolaudo/volumetry/data/`. Os resultados ficam na
versão `teste-volumetria` do repositório.
