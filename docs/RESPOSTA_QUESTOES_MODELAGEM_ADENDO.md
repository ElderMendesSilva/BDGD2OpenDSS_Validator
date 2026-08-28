# Adendo de modelagem — causa da não convergência com GD

**Conclusão:** a falha em alta irradiância não era do controle do inversor. Ela
vinha de transformadores cujo primário bifásico foi emitido como trifásico.
Fases sem alimentação ficavam perto de 0,50 pu; os inversores dessas barras
mudavam de comportamento no limiar de tensão e impediam a convergência.

## Evidência

- A BDGD declarava as fases do primário.
- Desligar apenas os inversores das barras defeituosas restaurava todos os
  passos da simulação; desligar a mesma quantidade em barras sadias não tinha
  efeito.
- O defeito persistia sem carga e sem geração, mostrando origem topológica.

## Correção e lição

O gerador de transformadores deve exigir fases compatíveis dos dois lados antes
de criar um enrolamento trifásico e deve usar a tensão correspondente ao número
de nós conectados. O caso reforça a regra do projeto: medir populações inteiras
e testar contrafactuais, em vez de concluir a partir de um único equipamento.

O mesmo ciclo também revelou que linhas de comprimento quase nulo e fontes de
AT fixas em 88 kV precisam de guarda explícita.
