# coefficient_pressuretoflow_eq_trainingandtest.py
import numpy as np
import os
import re
import pandas as pd

dt = 0.005  # 200 Hz
true_volume = 3.0  # Liters

def load_pressures_from_log(filepath):
    """Load a single .log file and return pressures array (Pa)."""
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
    # note: last column duplicates cbrt*sign — kept to match your original basis (you can remove one)
    return np.column_stack([
        np.ones_like(p),
        sign * sqrt_abs,
        p,
        p**2,
        cbrt_abs,
        p**3,
        log_abs,
        np.abs(p)**(1/3.0) * sign
    ])

def flow_from_p(p, coeffs):
    Phi = basis_functions(p)
    return Phi.dot(coeffs)


def generate_coefficients(folder, reg=1e-6):
    """
    Train coefficients from log files in a folder.
    Returns numpy array of coefficients.
    """
    pressures_all = []
    volumes_all = []

    for filename in sorted(os.listdir(folder)):
        if not filename.lower().endswith(".log"):
            continue
        filepath = os.path.join(folder, filename)
        p_pa = load_pressures_from_log(filepath)
        if p_pa.size == 0:
            continue
        pressures_all.append(p_pa)
        volumes_all.append(true_volume)

    if not pressures_all:
        raise ValueError("No valid log files found")

    # Build design matrix
    Phi = basis_functions(np.concatenate(pressures_all))
    b = np.repeat(volumes_all, [len(p) for p in pressures_all])

    # Regularized least squares
    n_basis = Phi.shape[1]
    A_reg = np.vstack([Phi, reg * np.eye(n_basis)])
    b_reg = np.concatenate([b, np.zeros(n_basis)])

    coeffs, *_ = np.linalg.lstsq(A_reg, b_reg, rcond=None)
    return coeffs

def evaluate_calibration(folder, coeffs):
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
        results.append((filename, V_liters, error_pct))
    return results



