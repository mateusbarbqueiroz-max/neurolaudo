# Guia: instalar o IsiX, ligar o botão do PACS e usar o NeuroLaudo

Tempo: cerca de 20 minutos. Nada aqui altera ou apaga o OsiriX MD.

O que eu conferi no código-fonte do IsiX: ele se registra para os links
`osirix://` e aceita todos os comandos de link do OsiriX, inclusive o de baixar
exames (`DownloadURL`).

O que conferi em um Mac de verdade (servidor do GitHub, macOS 27, IsiX 6.0.6):
o IsiX abre, o instalador do complemento funciona, o IsiX carrega o
complemento, e os comandos de Terminal do Passo 4 rodam sem erro. Com um **PACS
de teste** no lugar do PACS do hospital e um link no mesmo formato do seu (com
`ServerName` maiúsculo e valores entre aspas), o IsiX buscou o exame do fantoma,
abriu-o sozinho e, no segundo clique, não buscou de novo. A tela que apareceu
está em `docs/botao-pacs-simulado.png`.

O que **não** conferi: o seu PACS, a rede do hospital e o OsiriX MD disputando
o botão no mesmo Mac. Esse teste é o seu.

## Passo 1 — Instalar o IsiX

1. Abra <https://github.com/ThalesMMS/IsiX-DICOM-Viewer-macOS/releases>.
2. Na versão mais recente (6.0.6 ou mais nova), abra **Assets** e baixe o
   arquivo `.zip` de **Apple Silicon** (tem `Apple-Silicon` no nome).
3. Dê dois cliques no `.zip`. Arraste **IsiX DICOM Viewer** para a pasta
   **Aplicativos**.
4. Abra o IsiX. O macOS pergunta se pode abrir um programa baixado da internet:
   confirme.

O IsiX cria um banco de dados próprio (pasta `IsiX Data`). Se ele avisar que
encontrou um banco do Horos ou do OsiriX, é só um aviso: ele não abre nem
altera esse banco.

Use a 6.0.6 ou mais nova: foi a partir da 6.0.4 que o IsiX passou a entender o
link do botão do PACS como o OsiriX MD (pedido nosso ao autor, atendido em
19/11/2026).

## Passo 2 — Cadastrar o servidor do hospital no IsiX

O botão do PACS deste hospital manda o link no formato abaixo. Ele diz "busque
este exame no servidor tal, por DICOM, e depois abra":

```
osirix://?methodName=Retrieve&retrieveOnlyIfNeeded=yes&ServerName=XXX&filterKey=StudyInstanceUID&filterValue=XXX&then=Open
```

Por isso o IsiX precisa conhecer o servidor, como o OsiriX MD conhece.

1. No OsiriX MD, abra **Preferências > Locations** e anote do servidor do
   hospital: nome, endereço, AE Title e porta.
2. Ainda no OsiriX MD, em **Preferências > Listener**, anote o AE Title e a
   porta do próprio OsiriX.
3. No IsiX, em **Settings > Locations**, crie o servidor com os mesmos dados.
   Use o **mesmo nome** do OsiriX MD: é por ele (ou pelo AE Title do servidor)
   que o IsiX acha o servidor que o link pede.
4. No IsiX, em **Settings > Listener**, use o mesmo AE Title e a mesma porta
   que o OsiriX usa. O servidor do hospital só entrega exames a quem ele conhece
   por esse nome.

## Passo 3 — Ligar os links, só para este Mac

1. No IsiX, em **Settings > Listener**, marque **Activate the URL support and
   HTTP XML-RPC Server on port** (8080).
2. Em **Answer messages from**, escolha **This Mac only**.
3. Feche e abra o IsiX.

Não pule o item 2. Ao ligar os links, o IsiX também abre uma porta de comandos
para outros computadores, e de fábrica ela atende **qualquer endereço, sem
senha**. Um desses comandos devolve o conteúdo do banco, com nomes e
identificadores de pacientes. O botão do PACS não precisa disso: o link é
aberto no próprio Mac. O próprio IsiX avisa disso em vermelho nessa tela.

## Passo 4 — Passar o botão do PACS para o IsiX

Com o OsiriX MD instalado, os dois disputam o botão. Ao abrir de novo (fim do
Passo 3), o IsiX percebe que o OsiriX MD abre os links `osirix://` e mostra um
aviso, **Another application opens the links of IsiX DICOM Viewer** (pode
aparecer traduzido):

- **Make IsiX the Default**: o botão do PACS passa a abrir o IsiX. É o que
  queremos para o teste.
- **Not Now**: deixa como está.
- **Always at startup**: o IsiX toma os links de volta toda vez que abrir.
- **Don't ask again**: não pergunta mais.

Para conferir quem está com o botão, abra o **Terminal** (⌘ + espaço, digite
`Terminal`, Enter), cole o comando abaixo e aperte Enter:

```bash
osascript -l JavaScript -e 'ObjC.import("AppKit"); $.NSWorkspace.sharedWorkspace.URLForApplicationToOpenURL($.NSURL.URLWithString("osirix://teste")).path.js'
```

A resposta é o caminho de um programa; deve terminar em
`IsiX DICOM Viewer.app`.

Para **devolver** o botão ao OsiriX MD, cole no Terminal:

```bash
OSIRIX_ID="$(osascript -e 'id of app "OsiriX MD"')" && osascript -l JavaScript -e 'function run(a) { ObjC.import("CoreServices"); ObjC.bindFunction("LSSetDefaultHandlerForURLScheme", ["int", ["id", "id"]]); return String($.LSSetDefaultHandlerForURLScheme($("osirix"), $(a[0]))); }' "$OSIRIX_ID"
```

Se tiver marcado **Always at startup**, desmarque antes, em **Settings >
Listener** do IsiX (lá também se escolhe quais links o IsiX abre), senão o IsiX
toma o botão de volta na próxima vez que abrir.

## Passo 5 — Antes de testar

Feche o OsiriX MD: os dois programas usam a mesma porta DICOM e não podem ficar
abertos juntos.

## Passo 6 — Testar o botão

No PACS do hospital, abra um exame e clique no botão do OsiriX.

O que pode acontecer:

| Resultado | O que significa |
| --- | --- |
| O exame começa a chegar e abre sozinho logo que chega a primeira série, com todas as séries na coluna da esquerda; as outras continuam chegando | Funcionou (é o que se vê em `docs/botao-pacs-simulado.png`). Quem abre é o próprio IsiX. Para arrumar as séries pelo protocolo de neuro: **Plugins > Database > Protocolo de neuro**. |
| Clicar de novo no mesmo exame | Abre sem buscar de novo, porque o exame já está completo no Mac. |
| Aviso de servidor não encontrado | O nome do servidor em Settings > Locations não é o mesmo do OsiriX MD (Passo 2). |
| Aviso de que o pedido não foi enviado | O link pede algo que o IsiX não consegue buscar. Me avise, sem mandar o número do exame. |
| Aviso de que nada foi encontrado ou de falha na consulta | O servidor recusou o IsiX. Confira o AE Title e a porta do Passo 2. |
| O exame chega, mas não abre (aviso de que não chegou em 30 segundos) | A primeira série demorou. O exame fica na lista do IsiX. |
| Abre o OsiriX | O Passo 4 não pegou. |

## O que eu preciso que você me conte

1. O que aconteceu no Passo 6.
2. Os **nomes das séries** dos seus exames de rotina (RM de encéfalo e TC de
   crânio), como aparecem na lista do visualizador, por exemplo `AX FLAIR`,
   `DWI b1000`, `ADC`, `SWI`, `SAG T1 MPRAGE`. São nomes de protocolo, não
   dados de paciente. Preciso deles para o IsiX já abrir o exame arrumado para
   neuro.

## Passo 7 — Instalar o complemento NeuroLaudo

O complemento já compila no servidor Mac do GitHub, e lá o IsiX 6.0.3 o
carregou e ativou. Pode ser instalado antes do Passo 6. Com o IsiX fechado,
cole no Terminal:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mateusbarbqueiroz-max/neurolaudo/main/mac/instalar.sh)
```

Abra o IsiX. Em **Plugins > Plugins Manager** deve aparecer o NeuroLaudo. Os
comandos ficam nos menus **Plugins > Image Filters** (janelas), **Plugins > ROI
Tools** (medidas) e **Plugins > Database** (protocolo e comparação). A ajuda
está em **Plugins > Others > NeuroLaudo: ajuda**.

O complemento também abre sozinho, com as séries arrumadas pelo protocolo de
neuro, o exame que chega pela rede sem ter sido aberto pelo IsiX (por exemplo,
um exame que o PACS envia por conta própria). O exame do botão do PACS o IsiX
já abre; nele, o protocolo de neuro fica no menu. Para desligar ou religar:
**Plugins > Database > Abrir exame ao chegar: ligar ou desligar**.

## Passo 8 — Volumetria cerebral (opcional, uso em pesquisa)

A volumetria mede hipocampos, amígdalas, tálamos, ventrículos laterais, córtex,
substância branca e encéfalo em um T1 volumétrico e compara cada volume com o de
adultos saudáveis da mesma idade e sexo. **Não é validada para diagnóstico**: é
apoio, como o restante do NeuroLaudo. Os detalhes e o que já foi conferido
estão em `docs/VOLUMETRIA.md`.

**Instalar o motor (uma vez).** É um programa à parte, de cerca de 2 GB, que
fica em uma pasta só e não exige Xcode. Cole no Terminal e aguarde alguns
minutos:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/mateusbarbqueiroz-max/neurolaudo/main/mac/instalar-volumetria.sh)
```

No fim deve aparecer "Pronto. O motor de volumetria está em: …". Para remover,
basta apagar essa pasta.

**Usar.**

1. Abra no IsiX a série **T1 volumétrica (3D) sem contraste** do exame.
2. Menu **Plugins > Image Filters > Volumetria cerebral (pesquisa)…**.
3. Aguarde alguns minutos (em servidor de teste levou de um minuto e meio a
   dois e meio; no seu Mac ainda não foi medido). O IsiX continua utilizável
   enquanto isso.
4. Ao terminar, aparece um resumo com a frase pronta para colar (botão
   **Copiar**), e o exame ganha duas séries novas:
   - **NeuroLaudo: volumetria (pesquisa)**: o relatório, com a tabela, os
     percentis e os gráficos, e uma página de conferência;
   - **NeuroLaudo: mapa da segmentação (pesquisa)**: o T1 com as estruturas
     coloridas, corte a corte, que abre sozinho ao lado, no mesmo corte em que
     o T1 está (veja `docs/volumetria-no-isix.png`).
5. **Confira o mapa antes de usar os números**: cada estrutura no lugar e do
   lado certo. Hipocampo, amígdala e tálamo têm uma cor para cada lado
   justamente para que uma troca de lado apareça.
6. Percentil de estrutura pequena perto do limite (por exemplo, hipocampo no
   percentil 4 ou 6) deve ser lido como limítrofe: o método tem um ruído de
   1 a 3 % nessas estruturas.

O comando recusa séries que não servem (TC, série com poucos cortes, FLAIR,
difusão) e avisa quando o nome da série sugere contraste. A imagem não sai do
Mac: o motor roda nele, e os arquivos temporários são apagados no fim.

## Opcional — trazer exames antigos

No IsiX: **File > Import > Import Studies from Horos or OsiriX…**. Ele copia os
estudos para o banco dele e não mexe no banco do OsiriX.

## Lembrete

O IsiX não declara certificação para diagnóstico. Para laudo diagnóstico, o
OsiriX MD continua sendo o seu visualizador certificado.
