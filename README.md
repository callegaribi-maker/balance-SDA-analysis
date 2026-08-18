# Balance SDA App

Aplicativo Streamlit para processamento em lote de arquivos `.mat` contendo dados de plataforma de força e acelerômetro.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar

1. Crie um repositório no GitHub.
2. Envie `app.py`, `processing.py`, `requirements.txt` e `README.md`.
3. No Streamlit Community Cloud, escolha o repositório.
4. Main file path: `app.py`.
5. Deploy.

## Nome dos arquivos

Para reconhecimento automático, use preferencialmente nomes como:

- `S01_OA1.mat`
- `S01_OA2.mat`
- `S01_OF1.mat`
- `S01_OF2.mat`

OA = olhos abertos; OF = olhos fechados.
