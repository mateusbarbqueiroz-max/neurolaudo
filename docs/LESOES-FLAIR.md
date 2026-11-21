# Lesões de substância branca no FLAIR (estudo)

**Uso em pesquisa. Ainda não faz parte do NeuroLaudo**: é um estudo para decidir
se vale incluir a medida do volume de lesões, como o LesionQuant do NeuroQuant.

## O que é

O WMH-SynthSeg, do FreeSurfer 8.2 (Laso e colaboradores, 2024), é uma rede
neural que segmenta as hiperintensidades de substância branca e as estruturas do
encéfalo em FLAIR de qualquer aparelho, sem ajuste local. Ela devolve o volume das
lesões e um mapa delas.

## O que foi medido (21/11/2026)

**Memória.** O programa original calcula a rede inteira de uma vez e precisou de
mais de 16 GB. Ele derrubou o servidor Linux do GitHub, que tem 16 GB. No Mac do
GitHub, que tem 7 GB, rodou mais de uma hora sem terminar e foi cancelado.

**Versão por fatias** (`engine/scripts/wmh_lowmem.py`). Usa a mesma rede e os
mesmos pesos, mas calcula cada etapa em fatias de poucos cortes. A normalização
interna da rede usa a média e a variância do volume inteiro, calculadas antes,
como na original. Foi conferida contra a rede original em volumes pequenos, onde
a original cabe na memória: o mesmo rótulo em 100 % dos voxels, com diferença só
de arredondamento, em Linux e no Mac.

| Máquina | Tempo por exame | Memória |
| --- | --- | --- |
| Servidor Linux do GitHub (2 núcleos) | 7 a 8 minutos | 5,7 a 6,5 GB |
| Mac do GitHub (Apple Silicon virtual, 3 núcleos, 7 GB) | cerca de 10 minutos | 5,5 a 5,9 GB |

Os volumes saíram idênticos nas duas máquinas. No Mac novo, com 16 GB e mais
núcleos, deve levar poucos minutos; isso ainda não foi medido.

**O que a rede marca.** Em um voluntário saudável de 47 anos do ON-Harmony
(OpenNeuro ds004712, CC0), a rede marcou 4,4 mL de lesões no FLAIR do aparelho GE
e 9,0 mL no do Siemens, no mesmo mês. Quase tudo são os "caps" periventriculares
em torno dos cornos occipitais e frontais (`docs/lesoes-exemplo.png`, Siemens; em
vermelho, o que a rede marcou). Ou seja: em volumes pequenos, o número depende
muito do aparelho e da sequência, e inclui o que muitos leitores chamariam de
achado fisiológico.

**Repetição em 20 voluntários.** Os mesmos 20 voluntários saudáveis da
volumetria (19 a 50 anos), cada um em 6 aparelhos de 3 T (8 aparelhos no total:
Siemens Prisma e Trio, Philips Achieva e Ingenia, GE MR750 e Premier), e 9 deles
mais 5 vezes no mesmo aparelho. FLAIR 3D de cerca de 1 mm em todos; um voluntário
só tinha FLAIR 2D no GE MR750 e esse exame ficou de fora. Foram 164 exames, cerca
de 6 minutos cada no servidor Linux do GitHub (até 6,9 GB de memória).

| | Volume de lesões |
| --- | --- |
| Nos voluntários saudáveis | mediana 7,3 mL (2,6 a 19,0 mL) |
| Repetição no mesmo aparelho | variação de até ±2,3 mL (95 % das vezes) |
| Repetição em aparelhos diferentes | variação de até ±4,6 mL |

- **Saudável não é zero.** Todos os 20 tiveram pelo menos 2,6 mL. Os de 35 a
  50 anos ficaram, em média por pessoa, entre 7 e 16 mL; os de 19 a 29 anos,
  entre 3 e 8 mL.
- **O aparelho pesa.** Na média, cada aparelho desloca o volume entre −1,3 mL
  (GE MR750) e +1,3 mL (GE Premier). Na mesma pessoa, o volume chegou a dobrar
  de um aparelho para outro: 5,0 mL no Philips Achieva e 11,6 mL no Philips
  Ingenia, no mesmo voluntário de 25 anos.
- **Mudança pequena não aparece.** Uma lesão nova de esclerose múltipla costuma
  ter bem menos de 1 mL (uma esfera de 1 cm tem 0,5 mL). Mudanças desse tamanho
  ficam dentro da variação da própria medida, mesmo no mesmo aparelho. O volume
  total não substitui a comparação lesão a lesão.

O volume é a soma das probabilidades que a rede dá a cada voxel, como no
programa original. Contar só os voxels rotulados como lesão dá quase o mesmo
(mediana 6,9 mL; limites ±2,3 e ±4,6 mL).

## O que não dá para conferir daqui

- **Acurácia contra lesões marcadas à mão.** O banco público do desafio MICCAI
  WMH 2017 (FLAIR com lesões marcadas por especialistas) exige um termo assinado e
  enviado aos organizadores. Não achei outro banco com FLAIR e marcação manual
  sem cadastro.
- **Pacientes.** Os voluntários do ON-Harmony são jovens e saudáveis. Não há aqui
  exames com esclerose múltipla ou microangiopatia de verdade.

## O que falta decidir

- Se o volume de lesões, com essas características, é útil na prática do
  usuário (microangiopatia, esclerose múltipla, acompanhamento).
- Se vale validar a acurácia com o banco do desafio WMH, o que exige o termo
  assinado pelo usuário.

## Como repetir

No GitHub, aba Actions, fluxo "Lesões no FLAIR (estudo)": `etapa=viabilidade`
(dois exames, em Linux e no Mac) ou `etapa=repeticao` (20 voluntários). Os
resultados ficam na versão `teste-lesoes` do repositório.
