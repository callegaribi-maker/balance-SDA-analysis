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
        "Total_original": float(np.sum(np.sqrt(r))),  # fórmula do notebook original
        "Total_path": float(np.sum(np.sqrt(np.diff(ap)**2 + np.diff(ml)**2))),
        "RMS_AP": float(np.sqrt(np.mean(ap**2))),
        "RMS_ML": float(np.sqrt(np.mean(ml**2))),
        "Ellipse_area": area,
        "Ellipse_major_axis": major,
        "Ellipse_minor_axis": minor,
    }

def msd_curve(series, fs=FS):
    series = np.asarray(series, dtype=float)
    max_step = len(series)//2
    lags = np.arange(1, max_step+1, dtype=float)/fs
    msd = np.empty(max_step)
    for dt in range(1, max_step+1):
        d = series[dt:] - series[:-dt]
        msd[dt-1] = np.mean(d**2)
    return lags, msd

def sda_metrics(series, fs=FS):
    # Mesmo critério de CP do notebook original:
    # primeiro lag em que a derivada do MSD se torna negativa.
    lags, msd = msd_curve(series, fs)
    neg = np.flatnonzero(np.diff(msd) < 0)
    if len(neg) == 0:
        return {"CP_s": np.nan, "Slope_OL": np.nan,
                "OL_Sway": np.nan, "Slope_CL": np.nan}
    h1 = int(neg[0])
    cp, sway = float(lags[h1]), float(msd[h1])
    ol = float(np.polyfit(lags[:h1], msd[:h1], 1)[0]) if h1 >= 2 else np.nan
    cl = float(np.polyfit(lags[h1:-1], msd[h1:-1], 1)[0]) if len(lags[h1:-1]) >= 2 else np.nan
    return {"CP_s": cp, "Slope_OL": ol, "OL_Sway": sway, "Slope_CL": cl}

def parse_filename(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = re.search(r"(?i)(?:^|[_\-\s])(OA|OF|EO|EC)\s*[_\-]?\s*(\d+)?(?:$|[_\-\s])", stem)
    if not m:
        m = re.search(r"(?i)(OA|OF|EO|EC)(\d+)?", stem)
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

    fp = arr[0,0]
    fp_ap = _flatten_mat_field(fp["AP"])
    fp_ml = _flatten_mat_field(fp["ML"])
    nfp = min(len(fp_ap), len(fp_ml), 4501)
    fp_ap = bandpass(fp_ap[:nfp], FP_LOWCUT, FP_HIGHCUT)
    fp_ml = bandpass(fp_ml[:nfp], FP_LOWCUT, FP_HIGHCUT)

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
    raw = uploaded.getvalue()
    fp_ap, fp_ml, acc_ap, acc_ml = extract_mat_signals(io.BytesIO(raw))
    subject, condition, trial = parse_filename(uploaded.name)
    result = {"Arquivo": uploaded.name, "Subject": subject,
              "Condition": condition, "Trial": trial}

    for dev, ap, ml in [("FP", fp_ap, fp_ml), ("ACC", acc_ap, acc_ml)]:
        for k,v in global_metrics(ap,ml).items():
            result[f"{dev}_{k}"] = v

    fp_r = np.sqrt(fp_ap**2 + fp_ml**2)
    acc_r = np.sqrt(acc_ap**2 + acc_ml**2)
    for dev, sigs in [("FP", {"AP":fp_ap,"ML":fp_ml,"R":fp_r}),
                      ("ACC", {"AP":acc_ap,"ML":acc_ml,"R":acc_r})]:
        for axis, sig in sigs.items():
            for k,v in sda_metrics(sig).items():
                result[f"{dev}_{axis}_{k}"] = v
    return result

def make_summary(df):
    nums = df.select_dtypes(include=[np.number]).columns
    out=[]
    for c in nums:
        x=df[c]
        out.append({"Variavel":c,"N":int(x.notna().sum()),"Media":x.mean(),
                    "DP":x.std(ddof=1),"Mediana":x.median(),
                    "Min":x.min(),"Max":x.max()})
    return pd.DataFrame(out)

def mean_by_subject_condition(df):
    if not {"Subject","Condition"}.issubset(df.columns):
        return pd.DataFrame()
    numeric = list(df.select_dtypes(include=[np.number]).columns)
    if not numeric:
        return pd.DataFrame()
    return df.groupby(["Subject","Condition"], dropna=False)[numeric].mean().reset_index()
