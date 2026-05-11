"""Quick smoke test: verify risk_score trajectories for all 6 scenario×model combos."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from onnxruntime import InferenceSession

MODELS_DIR = ROOT / "ml" / "models"
MAX_TICKS = 20


def load(model_key):
    sess = InferenceSession(str(MODELS_DIR / f"model_{model_key}.onnx"))
    coef_data = json.loads((MODELS_DIR / f"model_{model_key}_coef.json").read_text())
    return sess, coef_data


def base_feats(model_type, tick):
    f = dict(
        gsr_phasic_peak_count=2.50, gsr_phasic_peak_freq=5.00,
        gsr_tonic_mean=0.80, gsr_tonic_slope=0.001,
        subject_norm_gsr_z=1.50,
        skin_temp_mean=32.00, skin_temp_derivative=0.001, subject_norm_st_z=0.00,
        acc_svm_mean=68.00, acc_svm_std=28.00, acc_svm_max=150.00,
        acc_svm_above_threshold_ratio=0.005,
        condition_lpe=1, condition_hpe=0,
        session_elapsed_ratio=tick / (MAX_TICKS - 1),
    )
    if model_type == "full":
        f.update(gaze_off_task_ratio=0.10, performance_failure_rate=0.95,
                 engagement_class_mode=2)
    return f


def gen_feats(scenario, model_type, tick):
    f = base_feats(model_type, tick)
    if scenario == "calm":
        noise = ((tick % 5) - 2) / 2
        f["gsr_phasic_peak_count"] = max(1.0, 2.5 + noise * 0.5)
        f["gsr_phasic_peak_freq"]  = max(2.0, 5.0 + noise * 1.0)
        f["gsr_tonic_slope"]       = noise * 0.0005
    elif scenario == "escalating":
        p = max(0.0, (tick - 4) / 15.0)
        f["gsr_phasic_peak_count"]         = 2.50 + p * 5.50
        f["gsr_phasic_peak_freq"]          = 5.00 + p * 11.00
        f["gsr_tonic_mean"]                = 0.80 + p * 1.00
        f["gsr_tonic_slope"]               = 0.001 + p * 0.039
        f["subject_norm_gsr_z"]            = 1.50 + p * (-2.00)
        f["skin_temp_mean"]                = 32.00 + p * (-0.50)
        f["skin_temp_derivative"]          = 0.001 + p * (-0.011)
        f["subject_norm_st_z"]             = 0.00 + p * (-0.50)
        f["acc_svm_mean"]                  = 68.00 + p * 12.00
        f["acc_svm_std"]                   = 28.00 + p * (-16.00)
        f["acc_svm_max"]                   = 150.00 + p * 50.00
        f["acc_svm_above_threshold_ratio"] = 0.005 + p * 0.045
        if model_type == "full":
            f["gaze_off_task_ratio"]       = 0.10 + p * 0.10
            f["engagement_class_mode"]     = round(max(0.0, 2.0 - p * 1.0))
    else:  # rapid_spike
        s = 0.0 if tick < 5 else 1.0 if tick == 5 else max(0.4, 1.0 - (tick - 5) * 0.12)
        f["gsr_phasic_peak_count"]         = 2.50 + s * 8.50
        f["gsr_phasic_peak_freq"]          = 5.00 + s * 17.00
        f["gsr_tonic_mean"]                = 0.80 + s * 1.50
        f["gsr_tonic_slope"]               = 0.001 + s * 0.089
        f["subject_norm_gsr_z"]            = 1.50 + s * (-3.50)
        f["acc_svm_mean"]                  = 68.00 + s * 12.00
        f["acc_svm_std"]                   = 28.00 + s * (-23.00)
        f["acc_svm_max"]                   = 150.00 + s * 50.00
        f["acc_svm_above_threshold_ratio"] = 0.005 + s * 0.115
        if model_type == "full":
            f["gaze_off_task_ratio"]       = 0.10 + s * 0.15
            f["engagement_class_mode"]     = round(max(0.0, 2.0 - s * 1.0))
    return f


def infer(sess, coef_data, feats):
    feat_names = coef_data["feature_names"]
    x = np.array([float(feats[n]) for n in feat_names], dtype=np.float32)
    out = sess.run(None, {"float_input": x.reshape(1, -1)})
    proba = out[1]
    if isinstance(proba, np.ndarray):
        return float(proba[0, 1])
    return float(proba[0][1])


PASS = True
for model_key in ["full", "wearable"]:
    sess, coef_data = load(model_key)
    print(f"\n=== {model_key.upper()} MODEL ===")
    print(f"{'tick':>4}  {'calm':>6}  {'escalating':>10}  {'rapid_spike':>11}")
    print("-" * 36)

    calm_scores = []
    esc_scores  = []
    spike_scores = []

    for tick in range(MAX_TICKS):
        c = infer(sess, coef_data, gen_feats("calm",        model_key, tick))
        e = infer(sess, coef_data, gen_feats("escalating",  model_key, tick))
        r = infer(sess, coef_data, gen_feats("rapid_spike", model_key, tick))
        calm_scores.append(c)
        esc_scores.append(e)
        spike_scores.append(r)
        print(f"  {tick:2d}  {c:6.3f}  {e:10.3f}  {r:11.3f}")

    # Milestone checks
    calm_max    = max(calm_scores)
    esc_final   = esc_scores[-1]
    spike_max   = max(spike_scores)

    ok_calm  = calm_max < 0.40
    ok_esc   = esc_final > 0.55
    ok_spike = spike_max > 0.70

    print(f"\n  Milestone check — {model_key}:")
    print(f"    calm_max={calm_max:.3f}  < 0.40  -> {'PASS' if ok_calm else 'FAIL'}")
    print(f"    esc_final={esc_final:.3f}  > 0.55  -> {'PASS' if ok_esc else 'FAIL'}")
    print(f"    spike_max={spike_max:.3f}  > 0.70  -> {'PASS' if ok_spike else 'FAIL'}")

    if not (ok_calm and ok_esc and ok_spike):
        PASS = False

print(f"\n{'ALL PASS' if PASS else 'SOME CHECKS FAILED'}")
sys.exit(0 if PASS else 1)
