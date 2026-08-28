# Execução no cluster Ubiratan

O ambiente usa PBS/OpenPBS: qsub, qstat e scripts em cluster/. A operação e as
responsabilidades estão em ENTRE_MAQUINAS.md.

## Preparação mínima

    git clone https://github.com/ElderMendesSilva/BDGD2OpenDSS_Validator.git
    cd BDGD2OpenDSS_Validator
    bash cluster/instalar.sh
    python doutor.py

O instalador cria .venv, instala as bibliotecas e testa pyogrio e OpenDSS. Em
nó sem rede, leve wheels e use bash cluster/instalar.sh --offline. O motor COM
da EPRI é exclusivo de Windows; no Linux há OpenDSS C-API, mas não confronto
entre dois motores.

## Antes de uma rodada

1. Confirmar que o nó está no commit pretendido e a fila está vazia/contada.
2. Definir BDGD2DSS_BASES apontando às .gdb.
3. Rodar o canário com Roraima e doutor.py.
4. Pedir no máximo o orçamento combinado de 64 núcleos e 192 GB.
5. Apenas Elder submete ou cancela jobs.

submeter_todas.sh deve primeiro mostrar o plano; --rodar é a confirmação
explícita de submissão. As correntes com depend=afterany limitam a
simultaneidade no próprio PBS.

## Execução e conferência

    qstat -q
    SUFIXO=VNN bash cluster/submeter_todas.sh
    SUFIXO=VNN bash cluster/submeter_todas.sh --rodar

O modo cluster não muda os cálculos nem os arquivos, apenas paralelismo e UI.
Resultados são válidos quando os JSONs/CSVs esperados existem e estão ligados a
um commit único — fila vazia não é critério de sucesso. A execução pode retomar
subestações e etapas já concluídas.
