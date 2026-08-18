# Balance SDA App — CP corrigido + exportação por botão

App Streamlit para processamento em lote de arquivos `.mat`.

## Exportação
Após processar os arquivos:
1. clique em **Gerar Excel**;
2. quando aparecer a confirmação, clique em **Baixar Excel**.

O Excel contém:
- Resultados_individuais
- Critical_Points
- Media_sujeito_condicao
- Resumo_geral
- Erros (quando houver)

## Critical Point
CP calculado pela interseção das regressões lineares:
- short-term: 0–0,5 s
- long-term: 2–10 s
