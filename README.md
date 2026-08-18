# Balance SDA App — CP corrigido

App Streamlit para processamento em lote de `.mat` com plataforma de força e acelerômetro.

## Critical Point

O CP é calculado pela **interseção das regressões lineares** do gráfico SDA linear-linear:

- short-term: 0–0,5 s
- long-term: 2–10 s

Essa lógica segue a descrição clássica de Collins & De Luca e implementações metodológicas posteriores.

## Arquivos esperados

- `app.py`
- `processing.py`
- `requirements.txt`
- `README.md`

## Publicar no Streamlit

1. Substitua no GitHub os arquivos antigos por estes.
2. Commit changes.
3. O Streamlit Cloud normalmente fará redeploy automaticamente.
4. Caso não faça: Manage app → Reboot app.

## Nomes sugeridos dos dados

- `S01_OA1.mat`
- `S01_OA2.mat`
- `S01_OF1.mat`
- `S01_OF2.mat`
