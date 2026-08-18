import io
import os
import re
import numpy as np
import pandas as pd
import scipy.io
from scipy.signal import butter, filtfilt
from scipy.interpolate import interp1d
from scipy.spatial import ConvexHull

FS = 100.0
FP_LOWCUT, FP_HIGHCUT = 0.1, 4.0
ACC_LOWCUT, ACC_HIGHCUT = 0.1, 3.0
FILTER_ORDER = 2

# Janelas clássicas para cálculo do CP no gráfico linear-linear do SDA
SHORT_TERM_WINDOW = (0.00, 0.50)
LONG_TERM_WINDOW = (2.00, 10.00)

def _flatten_mat_field(field):
    arr = np.asarray(field)
    while arr.dtype == object and arr.size == 1:
        arr = np.asarray(arr.flat[0])
    return np.asarray(arr).squeeze().astype(float)

def bandpass(signal, lowcut, highcut, fs=FS, order=FILTER_ORDER):
    signal = np.asarray(signal, dtype=float)
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype="band")
    return filtfilt(b, a, signal)

def ellipse_metrics(x, y, confidence=0.95):
    pts = np.column_stack((x, y))
    hull = ConvexHull(pts)
    boundary = pts[hull.vertices]
    cov = np.cov(boundary, rowvar=False)
    eigvals = np.maximum(np.linalg.eigvalsh(cov), 0)
    eigvals = np.sort(eigvals)[::-1]
    scale = np.sqrt(-2*np.log(1-confidence))/2
    axes = np.sqrt(eigvals)*scale
    major, minor = float(np.max(axes)), float(np.min(axes))
    return float(np.pi*major*minor), major, minor

def global_metrics(ap, ml):
    r = np.sqrt(ap**2 + ml**2)
    area, major, minor = ellipse_metrics(ml, ap)
    return {
        "Total_original": float(np.sum(np.sqrt(r))),
        "Total_path": float(np.sum(np.sqrt(np.diff(ap)**2 + np.diff(ml)**2))),
        "RMS_AP": float(np.sqrt(np.mean(ap**2))),
        "RMS_ML": float(np.sqrt(np.mean(ml**2))),
        "Ellipse_area": area,
        "Ellipse_major_axis": major,
        "Ellipse_minor_axis": minor,
    }

def msd_curve(series, fs=FS, max_lag_s=10.0):
    series = np.asarray(series, dtype=float)
    max_step = min(int(round(max_lag_s*fs)), len(series)//2)
    lags = np.arange(0, max_step+1, dtype=float) / fs
    msd = np.empty(max_step+1, dtype=float)
    msd[0] = 0.0
    for dt in range(1, max_step+1):
        d = series[dt:] - series[:-dt]
        msd[dt] = np.mean(d**2)
    return lags, msd

def _linear_fit_in_window(lags, msd, window):
    lo, hi = window
    mask = (lags >= lo) & (lags <= hi)
    x = lags[mask]
    y = msd[mask]
    if len(x) < 2:
        raise ValueError(f"Poucos pontos na janela {window}.")
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept), x, y

def sda_metrics(series, fs=FS,
                short_window=SHORT_TERM_WINDOW,
                long_window=LONG_TERM_WINDOW):
    """
    SDA clássico em escala linear-linear:
    - ajuste linear no regime short-term;
    - ajuste linear no regime long-term;
    - CP = interseção das duas retas.

    Diffusion coefficients são 1/2 da inclinação, conforme a literatura clássica.
    Também são retornadas as inclinações brutas das retas para comparação com o artigo.
    """
    lags, msd = msd_curve(series, fs=fs, max_lag_s=long_window[1])

    s_short, b_short, _, _ = _linear_fit_in_window(lags, msd, short_window)
    s_long, b_long, _, _ = _linear_fit_in_window(lags, msd, long_window)

    denom = s_short - s_long
    if np.isclose(denom, 0.0):
        cp_t = np.nan
        cp_msd = np.nan
    else:
        cp_t = (b_long - b_short) / denom
        cp_msd = s_short*cp_t + b_short

        # CP fora do domínio analisado é marcado como inválido
        if cp_t < 0 or cp_t > long_window[1]:
            cp_t = np.nan
            cp_msd = np.nan

    return {
        "CP_s": float(cp_t) if np.isfinite(cp_t) else np.nan,
        "CP_MSD": float(cp_msd) if np.isfinite(cp_msd) else np.nan,
        "Slope_OL": s_short,
        "Slope_CL": s_long,
        "D_short": s_short/2.0,
        "D_long": s_long/2.0,
    }

def parse_filename(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(?i)(OA|OF|EO|EC)\s*[_\-]?\s*(\d+)?", stem)
    condition, trial = "", ""
    subject = stem
    if m:
        raw = m.group(1).upper()
        condition = {"EO":"OA", "EC":"OF"}.get(raw, raw)
        trial = m.group(2) or ""
        subject = (stem[:m.start()] + stem[m.end():]).strip("_- ")
    return subject or stem, condition, trial

def extract_mat_signals(file_obj):
    data = scipy.io.loadmat(file_obj)
    if "dataToExport" not in data:
        raise ValueError("Arquivo sem a variável 'dataToExport'.")
    arr = data["dataToExport"]

    # Force platform
    fp = arr[0,0]
    fp_ap = _flatten_mat_field(fp["AP"])
    fp_ml = _flatten_mat_field(fp["ML"])
    nfp = min(len(fp_ap), len(fp_ml), 4501)
    fp_ap = bandpass(fp_ap[:nfp], FP_LOWCUT, FP_HIGHCUT)
    fp_ml = bandpass(fp_ml[:nfp], FP_LOWCUT, FP_HIGHCUT)

    # Accelerometer
    acc = arr[0,3]
    acc_ap = _flatten_mat_field(acc["accAP"])
    acc_ml = _flatten_mat_field(acc["accML"])
    acc_t = _flatten_mat_field(acc["Tempo"])
    n = min(len(acc_ap), len(acc_ml), len(acc_t))
    acc_ap, acc_ml, acc_t = acc_ap[:n], acc_ml[:n], acc_t[:n]

    order = np.argsort(acc_t)
    acc_t, acc_ap, acc_ml = acc_t[order], acc_ap[order], acc_ml[order]
    acc_t, idx = np.unique(acc_t, return_index=True)
    acc_ap, acc_ml = acc_ap[idx], acc_ml[idx]

    tnew = np.arange(acc_t[0], acc_t[-1], 1/FS)
    acc_ap = interp1d(acc_t, acc_ap, bounds_error=False, fill_value="extrapolate")(tnew)
    acc_ml = interp1d(acc_t, acc_ml, bounds_error=False, fill_value="extrapolate")(tnew)
    acc_ap = bandpass(acc_ap, ACC_LOWCUT, ACC_HIGHCUT)
    acc_ml = -bandpass(acc_ml, ACC_LOWCUT, ACC_HIGHCUT)

    return fp_ap, fp_ml, acc_ap, acc_ml

def process_uploaded_file(uploaded):
    fp_ap, fp_ml, acc_ap, acc_ml = extract_mat_signals(io.BytesIO(uploaded.getvalue()))
    subject, condition, trial = parse_filename(uploaded.name)

    result = {
        "Arquivo": uploaded.name,
        "Subject": subject,
        "Condition": condition,
        "Trial": trial
    }

    for dev, ap, ml in [("FP", fp_ap, fp_ml), ("ACC", acc_ap, acc_ml)]:
        for k,v in global_metrics(ap, ml).items():
            result[f"{dev}_{k}"] = v

    # CORREÇÃO: usa o resultante diretamente, sem raiz extra
    fp_r = np.sqrt(fp_ap**2 + fp_ml**2)
    acc_r = np.sqrt(acc_ap**2 + acc_ml**2)

    for dev, sigs in [
        ("FP", {"AP":fp_ap, "ML":fp_ml, "R":fp_r}),
        ("ACC", {"AP":acc_ap, "ML":acc_ml, "R":acc_r}),
    ]:
        for axis, sig in sigs.items():
            for k,v in sda_metrics(sig).items():
                result[f"{dev}_{axis}_{k}"] = v

    return result

def make_summary(df):
    nums = df.select_dtypes(include=[np.number]).columns
    out=[]
    for c in nums:
        x=df[c]
        out.append({
            "Variavel":c,
            "N":int(x.notna().sum()),
            "Media":x.mean(),
            "DP":x.std(ddof=1),
            "Mediana":x.median(),
            "Min":x.min(),
            "Max":x.max()
        })
    return pd.DataFrame(out)

def mean_by_subject_condition(df):
    numeric = list(df.select_dtypes(include=[np.number]).columns)
    if not numeric:
        return pd.DataFrame()
    return (
        df.groupby(["Subject","Condition"], dropna=False)[numeric]
          .mean()
          .reset_index()
    )
