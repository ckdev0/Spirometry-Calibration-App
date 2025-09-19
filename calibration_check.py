# calibration.py
import numpy as np
import os
import re
import pandas as pd

dt = 0.005  # 200 Hz
true_volume = 3.0  # Liters
coeffs = np.array([7.27864417e-05, -9.27587037e-04,  3.19441219e-05, -4.58356939e-09,
                   5.48499358e-04, -4.92505941e-12, -5.79998850e-04,  1.27632466e-03])

#[7.27864417e-05, -9.27587037e-04,  3.19441219e-05, -4.58356939e-09, 5.48499358e-04, -4.92505941e-12, -5.79998850e-04,  1.27632466e-03]

def load_pressures_from_log(filepath):
    pressures_pa = []
    with open(filepath, "r") as f:
        for line in f:
            start_pos = line.find('[')
            end_pos = line.find(']')
            if start_pos != -1 and end_pos != -1:
                frame_data = line[start_pos + 1:end_pos]
                frame_data_split = frame_data.split(":")
                try:
                    ADCvalues_array = [int(x, 16) for x in frame_data_split]
                except ValueError:
                    continue
                OS_dig = 0.5 * (2**24)
                FSS_inH2O = 120
                for i in range(7, 107, 5):
                    if i + 4 < len(ADCvalues_array):
                        pos3 = ADCvalues_array[i + 2] & 0xFF
                        pos2 = ADCvalues_array[i + 3] & 0xFF
                        pos1 = ADCvalues_array[i + 4] & 0xFF
                        pos3 = pos3 << 16
                        pos2 = pos2 << 8
                        decimal_count = pos3 | pos2 | pos1
                        pressure_inH2O = 1.25 * ((decimal_count - OS_dig) / (2**24)) * FSS_inH2O
                        pressure_pa = pressure_inH2O * 249.089
                        pressures_pa.append(pressure_pa)
    return np.array(pressures_pa)

def basis_functions(p):
    p = np.asarray(p)
    sign = np.sign(p)
    sqrt_abs = np.sqrt(np.abs(p))
    cbrt_abs = np.cbrt(np.abs(p))
    log_abs = np.log1p(np.abs(p))
    return np.column_stack([
        np.ones_like(p),
        sign * sqrt_abs,
        p,
        p**2,
        cbrt_abs,
        p**3,
        log_abs,
        np.cbrt(np.abs(p)) * np.sign(p),
    ])

def flow_from_p(p, coeffs):
    Phi = basis_functions(p)
    q = Phi.dot(coeffs)  # Flow in L/s
    return q

def get_time_from_filename(filename):
    match = re.search(r'(\d+(?:\.\d+)?)(?=\.log$)', filename)
    if match:
        return float(match.group(1))
    return None

def run_calibration(folder):
    results = []
    for filename in sorted(os.listdir(folder)):
        if not filename.lower().endswith(".log"):
            continue
        filepath = os.path.join(folder, filename)
        p_pa = load_pressures_from_log(filepath)
        if p_pa.size == 0:
            continue
        q_ls = flow_from_p(p_pa, coeffs)
        V_liters = np.sum(q_ls) * dt
        error_pct = ((V_liters - true_volume) / true_volume) * 100
        t_from_name = get_time_from_filename(filename)
        results.append((filename, V_liters, error_pct, t_from_name))

    df = pd.DataFrame([{
        "Filename": fname,
        "Volume (L)": round(vol, 3),
        "Error (%)": round(err, 2),
        "Time (s)": t
    } for fname, vol, err, t in results])

    failed_cases = df[(df["Error (%)"] > 3) | (df["Error (%)"] < -3)]
    success = failed_cases.empty

    return df, success, failed_cases

# coefficient_pressuretoflow_eq_trainingandtest.py

def load_pressures_from_logs(log_folder):
    """Load pressures from all log files in a folder"""
    all_pressures = []
    for filename in sorted(os.listdir(log_folder)):
        if not filename.lower().endswith(".log"):
            continue
        filepath = os.path.join(log_folder, filename)
        pressures = load_pressures_from_log(filepath)
        if pressures.size > 0:
            all_pressures.append(pressures)
    return all_pressures

def build_design_matrix(pressures_list, dt):
    """Build design matrix for least squares fitting"""
    A_rows = []
    for pressures in pressures_list:
        q_ls = flow_from_p(pressures, np.zeros(8))  # Use zero coeffs to get basis functions
        Phi = basis_functions(pressures)
        A_rows.append(Phi)
    
    if A_rows:
        A = np.vstack(A_rows)
    else:
        # Return empty matrix with correct shape if no data
        A = np.zeros((0, 8))
    
    return A

def generate_coefficients(log_folder, dt=0.005, true_volume=3.0):
    train_pressures = load_pressures_from_logs(log_folder)
    A_train = build_design_matrix(train_pressures, dt)
    b_train = np.full((A_train.shape[0],), true_volume)
    reg = 1e-6
    n_basis = A_train.shape[1]
    A_reg = np.vstack([A_train, reg * np.eye(n_basis)])
    b_reg = np.concatenate([b_train, np.zeros(n_basis)])
    coeffs, *_ = np.linalg.lstsq(A_reg, b_reg, rcond=None)
    return coeffs
