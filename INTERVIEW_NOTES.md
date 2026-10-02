# Notas de entrevista (PT-BR)

> Projeto 100% **sintético**: empresa fictícia ("Vaultly"), dados gerados por simulador com seed fixa. Os números abaixo vêm da execução do código (`make all`); não são resultados do mundo real.

## As 3 decisões técnicas mais importantes

1. **Warehouse em snowflake (DuckDB) com marts em SQL por cima.** As dimensões têm hierarquias reais (data→mês→trimestre→ano, país→região, canal→campanha, plano→tier), e os fatos têm granularidades diferentes (anúncio mensal, uso diário, evento com timestamp). Normalizar dá chaves conformadas (`dim_month`, `dim_country`) e regras de negócio em um só lugar (free vs paid). O custo são mais joins; por isso os marts escondem esses joins e entregam tabelas "tipo estrela" para análise.
2. **Razões sempre recalculadas a partir de somas, e janelas sempre relativas a um `as_of_date`.** CTR, CPC, CPM, taxa de signup e custo por signup nunca são médias de razões de linha; nenhuma query usa `current_date`/`now()` (há teste que garante isso). Isso torna resultados reproduzíveis e evita o viés clássico de Simpson/peso por linha.
3. **O modelo de propensão foi desenhado contra vazamento.** Alvo = converter em pago nos *próximos* 30 dias; features só dos *60 dias anteriores* ao snapshot; split por tempo com purge (nenhuma janela de rótulo do treino toca o teste); seleção de modelo, calibração e threshold na dobra de validação; threshold por **lucro esperado**, não por acurácia.

## 5 perguntas prováveis (com respostas)

**1. Por que snowflake e não star?**
Porque há hierarquias reais usadas em roll-ups e regras (free/paid, canal pago) que ficam em uma linha só. Trade-offs: mais joins, SQL mais longo, mais integridade a manter (FK + checks de qualidade), e consumo mais difícil por BI direto. Aqui o volume torna o custo irrelevante e os marts funcionam como camada estrela. Se uma ferramenta de BI apontasse direto para o modelo, ou o fato fosse enorme, eu publicaria uma estrela desnormalizada. Atributos que mudam (plano) ficam no `fact_subscription_event` (event log) e a view `mart_subscription_history` gera intervalos estilo SCD2 com `LEAD()`; `dim_user.current_plan_key` é tipo 1.

**2. Razão de somas vs média de razões?**
Média de razões dá o mesmo peso a uma linha com 100 impressões e a uma com 10 milhões; o CTR agregado correto é Σcliques/Σimpressões. Há teste unitário com um caso onde a média ingênua erra por mais de 10 pontos percentuais. Mesma regra para custo por signup (Σgasto/Σsignups) e nos intervalos de confiança: o bootstrap reamostra linhas e recalcula a razão de somas. Ressalva: *reach* não é aditivo; a frequência agregada (impressões/alcance) é aproximação e está documentada.

**3. Onde estava o vazamento (leakage) no modelo?**
No caderno original o alvo ("heavy user") era definido a partir da mesma variável usada como feature, então o modelo "acertava" por construção. Aqui há uma demonstração reproduzível (`leakage_demo`): um alvo definido por `assets_30d` com `assets_30d` como entrada dá ROC-AUC ≈ 1, e isso não significa nada. No modelo real o alvo é um evento futuro (upgrade em (snapshot, snapshot+30d]) e as features usam só dias ≤ snapshot; um teste de SQL confere que nenhuma linha de feature é de usuário que já era pago no snapshot. Resultado honesto, bem mais modesto: PR-AUC de hold-out ≈ 0,105 contra taxa-base ≈ 0,006 (cerca de 17x), ROC-AUC ≈ 0,90, lift de ≈ 6,8x no decil superior.

**4. Custo por signup vs CAC pago?**
Custo por signup = gasto / contas gratuitas criadas; CAC pago = gasto / clientes que pagam. Em média o CAC pago é ~30x o custo por signup (EUR ~295 vs ~10), porque só uma fração pequena dos signups converte. Usar custo por signup para decidir orçamento esconde que países baratos por signup (BR, MX, CO, PE, AR) têm LTV/CAC abaixo de 3x enquanto os EUA ficam em ~5,3x. O CAC usa só coortes maduras (90 dias completos) para evitar viés de censura à direita, e mostro IC de Poisson porque alguns países têm poucas dezenas de clientes.

**5. Como a recomendação de limite depende das premissas?**
A parte de uso é medida (quem passa do limite, quanto volume). A parte de dinheiro não: conversão dos bloqueados, risco de perda de usuário e valor de um usuário gratuito retido são cenários (baixo/base/alto) em `config/analysis.yaml`. No limite recomendado (mensal de 50 ativos, ~17,6% dos usuários gratuitos ativos afetados), o MRR incremental esperado vai de EUR −1,5 mil (baixo) a +4,7 mil (alto), com +1,5 mil no base: **o sinal muda entre cenários**, então a conclusão é uma hipótese para teste A/B. Além disso, o ótimo é limitado por um guard-rail (≤20% de afetados): sem ele o modelo linear sempre empurraria o limite para baixo, algo que ele não tem como validar. O simulador do dashboard deixa mexer em todas as premissas.

## Limitações conhecidas

- Dados sintéticos refletem as relações que eu programei; dados reais têm ruído, drift e lacunas de atribuição.
- CAC baseado em signups atribuídos pela plataforma; sem incrementalidade nem atribuição multitouch.
- LTV com churn constante; a curva real de retenção pode ser diferente.
- Poucos positivos por snapshot: threshold e calibração são ruidosos; os valores em euros do lucro dependem de premissas inventadas (a ordem das políticas é mais confiável que o valor).
- O modelo prevê *quem converte*, não *quem é persuadido*; o próximo passo é uplift modeling ou teste randomizado.
- O modelo escolhido pode mudar com a seed/hiperparâmetros (regressão logística e gradient boosting ficam próximos); a seleção é feita na validação, não no teste.
- Valores visuais provisórios: cores de status (ok/warn/alert), tons derivados e o símbolo "A" (não achei o arquivo oficial) estão em um único arquivo (`app/theme.py`).
