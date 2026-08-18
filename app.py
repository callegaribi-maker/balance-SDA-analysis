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

# Mantém resultados enquanto o usuário interage com os botões
if "df" not in st.session_state:
    st.session_state.df = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "means" not in st.session_state:
    st.session_state.means = None
if "cp" not in st.session_state:
    st.session_state.cp = None
if "errors" not in st.session_state:
    st.session_state.errors = []

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
        progress.progress((i + 1) / len(files))

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
    cp = df[["Arquivo", "Subject", "Condition", "Trial"] + cpcols]

    st.session_state.df = df
    st.session_state.summary = summary
    st.session_state.means = means
    st.session_state.cp = cp
    st.session_state.errors = errors

    st.success(f"{len(df)} arquivo(s) processado(s).")

# Exibe resultados após o processamento
if st.session_state.df is not None:
    df = st.session_state.df
    summary = st.session_state.summary
    means = st.session_state.means
    cp = st.session_state.cp
    errors = st.session_state.errors

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

    st.divider()
    st.subheader("Exportar resultados")

    if st.button("Gerar Excel"):
        try:
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(
                    writer,
                    sheet_name="Resultados_individuais",
                    index=False
                )

                cp.to_excel(
                    writer,
                    sheet_name="Critical_Points",
                    index=False
                )

                if means is not None and not means.empty:
                    means.to_excel(
                        writer,
                        sheet_name="Media_sujeito_condicao",
                        index=False
                    )

                if summary is not None and not summary.empty:
                    summary.to_excel(
                        writer,
                        sheet_name="Resumo_geral",
                        index=False
                    )

                if errors:
                    pd.DataFrame(errors).to_excel(
                        writer,
                        sheet_name="Erros",
                        index=False
                    )

            st.session_state["excel_bytes"] = output.getvalue()
            st.success("Excel gerado com sucesso.")

        except Exception as e:
            st.error("Erro ao gerar o Excel.")
            st.exception(e)

    if "excel_bytes" in st.session_state:
        st.download_button(
            label="Baixar Excel",
            data=st.session_state["excel_bytes"],
            file_name="resultados_balance_sda.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
