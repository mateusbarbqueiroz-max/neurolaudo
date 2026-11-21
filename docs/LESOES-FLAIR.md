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

**Repetição em 20 voluntários.** Em andamento: os mesmos 20 voluntários da
volumetria, em 6 aparelhos de 3 T, e 10 deles mais 5 vezes no mesmo aparelho
(`lesoes.yml -f etapa=repeticao`).

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
