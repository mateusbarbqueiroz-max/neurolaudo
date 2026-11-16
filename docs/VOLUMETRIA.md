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
- uma frase pronta para colar no laudo, já com a ressalva de uso em pesquisa.

Exemplo do relatório, com um voluntário de banco público: `docs/exemplo-volumetria.png`.

## Como funciona

1. **No IsiX**, o comando *Plugins > Image Filters > Volumetria cerebral
   (pesquisa)…* copia os cortes da série aberta para um arquivo de volume. A
   posição e a orientação de cada corte vêm do próprio exame.
2. **O motor** (programa em Python instalado à parte, `mac/instalar-volumetria.sh`)
   repete os passos usados para construir a referência:
   - localiza o encéfalo (SynthStrip);
   - recorta a imagem em volta dele, com 15 mm de margem;
   - segmenta com o SynthSeg 2.0 em modo rápido, no processador;
   - compara cada volume com a referência por idade e sexo.
3. **De volta ao IsiX**, o complemento grava no exame duas séries novas (o
   relatório e o mapa colorido), abre o mapa e mostra o resumo.

A imagem não sai do Mac. A pasta temporária, com a imagem e o nome do paciente,
é apagada no fim, dê certo ou não.

## De onde vêm os programas e a referência

| Peça | Origem | Licença |
| --- | --- | --- |
| `mri_synthseg` e `mri_synthstrip` | FreeSurfer 8.2.0, baixados do repositório oficial e conferidos por soma SHA-256 | licença do FreeSurfer; SynthSeg, Apache 2.0 |
| Modelos treinados (SynthSeg 2.0 e SynthStrip) | servidor oficial do FreeSurfer, conferidos por soma SHA-256 | idem |
| Biblioteca `surfa` 0.6.3 | FreeSurfer; compilada pelo projeto para Mac, porque só existe em código-fonte | MIT |
| Referência (normas) | Neurodesk, `recipes/synthseg/brainquant_norms.json`: 561 adultos saudáveis do banco IXI, de 20 a 86 anos | MIT; dados do IXI, CC BY-SA 3.0 |

Não é a instalação completa do FreeSurfer (20 GB): o instalador baixa só essas
peças, cerca de 2,5 GB com o Python e as bibliotecas.

## Decisões e porquês

- **Mesmos passos da referência.** Um percentil só vale se o volume do paciente
  for medido do mesmo jeito que os volumes da referência. Por isso o motor
  repete o recorte de 15 mm e as opções `--fast --cpu`.
- **Sem as notas automáticas de qualidade do SynthSeg.** Medido no exame público
  IXI002: com as notas (`--qc`) os volumes deixam de ser idênticos aos da
  referência (até 1,3 % de diferença no córtex) e a memória necessária estoura.
  Ficam como opção (`--qualidade`), desligada. A conferência de qualidade é a
  do olho: a página e a série coloridas.
- **Cores diferentes para cada lado** em hipocampo, amígdala e tálamo, e letras
  D e E nas imagens: uma troca de lado tem de aparecer na imagem.
- **Trava de orientação.** O complemento calcula a orientação do volume que
  gravou, e o motor informa a que leu do arquivo. Se as duas não baterem, nada
  é gravado no exame.
- **Recusas.** O comando não roda em TC, em série com menos de 60 cortes, em
  série com cortes faltando ou repetidos, nem em FLAIR, difusão e afins. Avisa
  quando o nome da série sugere contraste ou não é reconhecido como T1.

## Limites do método

- A referência cobre adultos de 20 a 86 anos. Fora disso o relatório avisa que
  os percentis são extrapolados. Não serve para crianças.
- Entre aparelhos diferentes o resultado pode deslocar até cerca de 0,5
  desvio-padrão (estimativa do Neurodesk).
- É medida de um único momento: não mede perda ao longo do tempo.
- A referência é de T1 sem contraste, com voxel de cerca de 1 mm. Acima de
  1,5 mm o relatório avisa.
- A segmentação pode errar em anatomia muito alterada (grandes lesões, cirurgia,
  hidrocefalia acentuada). Por isso a conferência visual é parte do uso.
