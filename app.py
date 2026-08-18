import io
import pandas as pd
import streamlit as st
from processing import (
    process_uploaded_file,
    make_summary,
    mean_by_subject_condition
)

st.set_page_config(page_title="Balance SDA", layout="wide")
st.title("Balance / SDA — processamento em lote")
st.caption("Force Platform + Accelerometer | AP, ML e R")

st.info(
    "Critical Point (CP) calculado pela interseção das regressões lineares "
    "dos regimes short-term (0–0,5 s) e long-term (2–10 s) no gráfico MSD × Δt "
    "em escala linear-linear."
)

files = st.file_uploader(
    "Selecione vários arquivos .mat",
    type=["mat"],
    accept_multiple_files=True
)

if files and st.button("Processar arquivos", type="primary"):
    rows = []
    errors = []
    progress = st.progress(0)

    for i, f in enumerate(files):
        try:
            rows.append(process_uploaded_file(f))
        except Exception as e:
            errors.append({"Arquivo": f.name, "Erro": str(e)})
        progress.progress((i+1)/len(files))

    if errors:
        st.warning(f"{len(errors)} arquivo(s) apresentaram erro.")
        st.dataframe(pd.DataFrame(errors), use_container_width=True)

    if len(rows) == 0:
        st.error(
            "Nenhum arquivo foi processado com sucesso. "
            "Veja a tabela de erros acima."
        )
        st.stop()

    df = pd.DataFrame(rows)
    summary = make_summary(df)
    means = mean_by_subject_condition(df)

    cpcols = [
        c for c in df.columns
        if c.endswith("_CP_s") or c.endswith("_CP_MSD")
    ]
    cp = df[["Arquivo","Subject","Condition","Trial"] + cpcols]

    st.success(f"{len(df)} arquivo(s) processado(s).")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Resultados individuais",
        "Critical Points",
        "Média por sujeito/condição",
        "Resumo geral"
    ])

    with tab1:
        st.dataframe(df, use_container_width=True)

    with tab2:
        st.dataframe(cp, use_container_width=True)

    with tab3:
        st.dataframe(means, use_container_width=True)

    with tab4:
        st.dataframe(summary, use_container_width=True)

    # EXPORTAÇÃO ROBUSTA:
    # sempre cria pelo menos uma planilha antes de salvar o workbook.
    output = io.BytesIO()

    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            wrote_sheet = False

            if not df.empty:
                df.to_excel(writer, "Resultados_individuais", index=False)
                wrote_sheet = True

            if not cp.empty:
                cp.to_excel(writer, "Critical_Points", index=False)
                wrote_sheet = True

            if not means.empty:
                means.to_excel(writer, "Media_sujeito_condicao", index=False)
                wrote_sheet = True

            if not summary.empty:
                summary.to_excel(writer, "Resumo_geral", index=False)
                wrote_sheet = True

            if errors:
                pd.DataFrame(errors).to_excel(writer, "Erros", index=False)
                wrote_sheet = True

            if not wrote_sheet:
                pd.DataFrame({
                    "Mensagem": ["Nenhum resultado disponível."]
                }).to_excel(writer, "Informacao", index=False)

        st.download_button(
            "Baixar resultados em Excel",
            data=output.getvalue(),
            file_name="resultados_balance_sda.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error("Erro ao gerar o arquivo Excel.")
        st.exception(e)
