# Origem das normas de volumetria

`brainquant_norms.json` (e `engine/tests/data/brainquant_ixi_volumes.csv`) foram
copiados sem alteração de `recipes/synthseg/` do repositório
<https://github.com/neurodesk/neurocontainers>, commit
`c66847eed4522cbb702701f6ae14a51b1e2ea6e3` (14/11/2026).

- Código e arquivos do Neurodesk: licença MIT, © 2021 NeuroDesk.
- As normas derivam do conjunto IXI (<https://brain-development.org/ixi-dataset/>),
  licença CC BY-SA 3.0: atribuição obrigatória e compartilhamento pela mesma licença.

O que as normas são: 561 adultos saudáveis de 20 a 86 anos (311 mulheres, 250
homens), três aparelhos de 1,5 T e 3 T em Londres, segmentados com o SynthSeg 2.0
em modo rápido (`mri_synthseg --fast --cpu --vol`, FreeSurfer 8.2.0), após
recorte pela caixa do SynthStrip com margem de 15 mm.

Limites declarados pelos autores:
- valem só para volumes medidos do mesmo jeito (mesmo programa e mesmo modo);
- entre aparelhos, o resultado pode deslocar até cerca de 0,5 desvio-padrão;
- fora de 20 a 86 anos, o percentil é extrapolação;
- população de voluntários de Londres; corte transversal, não mede perda ao longo do tempo;
- uso em pesquisa, não validado para diagnóstico.
