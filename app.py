import io
import pandas as pd
import streamlit as st
from processing import process_uploaded_file, make_summary, mean_by_subject_condition

st.set_page_config(page_title="Balance SDA", layout="wide")
st.title("Balance / SDA — processamento em lote")
st.caption("Force Platform + Accelerometer | AP, ML e R")

st.info(
    "O Critical Point segue o critério do notebook original: primeiro lag em que "
    "a derivada do MSD se torna negativa. O código corrige o uso do resultante R "
    "e o cruzamento indevido de arrays FP/ACC identificado no notebook original."
)

files = st.file_uploader(
    "Selecione vários arquivos .mat",
    type=["mat"],
    accept_multiple_files=True
)

if files and st.button("Processar arquivos", type="primary"):
    rows, errors = [], []
    progress = st.progress(0)
    for i, f in enumerate(files):
        try:
            rows.append(process_uploaded_file(f))
        except Exception as e:
            errors.append({"Arquivo": f.name, "Erro": str(e)})
        progress.progress((i+1)/len(files))

    if not rows:
        st.error("Nenhum arquivo foi processado.")
        if errors:
            st.dataframe(pd.DataFrame(errors), use_container_width=True)
        st.stop()

    df = pd.DataFrame(rows)
    summary = make_summary(df)
    means = mean_by_subject_condition(df)
    cpcols = [c for c in df.columns if c.endswith("_CP_s")]
    cp = df[["Arquivo","Subject","Condition","Trial"] + cpcols]

    st.success(f"{len(df)} arquivo(s) processado(s).")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Resultados individuais", "Critical Points",
        "Média por sujeito/condição", "Resumo geral"
    ])
    with tab1:
        st.dataframe(df, use_container_width=True)
    with tab2:
        st.dataframe(cp, use_container_width=True)
    with tab3:
        st.dataframe(means, use_container_width=True)
    with tab4:
        st.dataframe(summary, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, "Resultados_individuais", index=False)
        cp.to_excel(writer, "Critical_Points", index=False)
        means.to_excel(writer, "Media_sujeito_condicao", index=False)
        summary.to_excel(writer, "Resumo_geral", index=False)
        if errors:
            pd.DataFrame(errors).to_excel(writer, "Erros", index=False)

    st.download_button(
        "Baixar resultados em Excel",
        output.getvalue(),
        file_name="resultados_balance_sda.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    if errors:
        st.warning(f"{len(errors)} arquivo(s) apresentaram erro.")
        st.dataframe(pd.DataFrame(errors), use_container_width=True)
