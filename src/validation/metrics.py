"""
Geospatial, Photogrammetric, and Classification Validation Metrics (Module 7 Component)

Calculates comprehensive accuracy, error rates, and confusion matrix statistics:
- Full Confusion Matrix: TP, FP, TN, FN
- Accuracy, Precision (PPV), Recall (Sensitivity / TPR), Specificity (TNR), F1-Score, IoU
- False Positive Rate (FPR), False Negative Rate (FNR), False Discovery Rate (FDR)
- Matthews Correlation Coefficient (MCC)
- Elevation RMSE, MAE, Max Absolute Error
- Slope-angle error distribution in degrees
- Image Super-Resolution PSNR (dB) and SSIM
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import numpy as np
from skimage.metrics import structural_similarity as ssim_func
from skimage.metrics import peak_signal_noise_ratio as psnr_func


def compute_confusion_matrix_and_rates(
    pred_binary_mask: np.ndarray,
    target_binary_mask: np.ndarray,
) -> Dict[str, Any]:
    """
    Computes complete 2x2 confusion matrix and derived accuracy/error rates.
    
    Positive Class = Hazard (1 / True)
    Negative Class = Safe (0 / False)
    """
    p_bool = pred_binary_mask.astype(bool).flatten()
    t_bool = target_binary_mask.astype(bool).flatten()

    tp = int(np.sum(p_bool & t_bool))
    fp = int(np.sum(p_bool & ~t_bool))
    fn = int(np.sum(~p_bool & t_bool))
    tn = int(np.sum(~p_bool & ~t_bool))
    total = tp + fp + fn + tn

    # Classification Metrics
    accuracy = float((tp + tn) / total) if total > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    f1_score = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    iou = float(tp / (tp + fp + fn)) if (tp + fp + fn) > 0 else 1.0

    # Error Rates
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0  # False Alarm Rate
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0  # Missed Hazard Rate
    fdr = float(fp / (fp + tp)) if (fp + tp) > 0 else 0.0  # False Discovery Rate

    # Matthews Correlation Coefficient (MCC)
    denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    mcc = float((tp * tn - fp * fn) / denom) if denom > 0 else 0.0

    return {
        "confusion_matrix": {
            "true_positive_hazard": tp,
            "false_positive_hazard": fp,
            "false_negative_hazard": fn,
            "true_negative_safe": tn,
            "total_pixels": total,
        },
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall_sensitivity": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1_score": round(f1_score, 4),
        "iou_jaccard": round(iou, 4),
        "false_positive_rate_fpr": round(fpr, 4),
        "false_negative_rate_fnr": round(fnr, 4),
        "false_discovery_rate_fdr": round(fdr, 4),
        "matthews_corr_coef_mcc": round(mcc, 4),
    }


def compute_elevation_metrics(pred_dem: np.ndarray, target_dem: np.ndarray) -> Dict[str, float]:
    """Computes RMSE, MAE, and max absolute elevation error in meters."""
    diff = pred_dem.astype(np.float64) - target_dem.astype(np.float64)
    valid_mask = np.isfinite(diff)

    if not np.any(valid_mask):
        return {"rmse_m": float("nan"), "mae_m": float("nan"), "max_error_m": float("nan")}

    diff_valid = diff[valid_mask]
    rmse = float(np.sqrt(np.mean(diff_valid**2)))
    mae = float(np.mean(np.abs(diff_valid)))
    max_err = float(np.max(np.abs(diff_valid)))

    return {
        "rmse_m": round(rmse, 4),
        "mae_m": round(mae, 4),
        "max_error_m": round(max_err, 4),
    }


def compute_slope_error_metrics(pred_slope: np.ndarray, target_slope: np.ndarray) -> Dict[str, float]:
    """Computes slope angle error statistics in degrees."""
    diff = np.abs(pred_slope.astype(np.float64) - target_slope.astype(np.float64))
    valid = diff[np.isfinite(diff)]
    if len(valid) == 0:
        return {"slope_mae_deg": float("nan"), "slope_p95_err_deg": float("nan")}

    return {
        "slope_mae_deg": round(float(np.mean(valid)), 4),
        "slope_p95_err_deg": round(float(np.percentile(valid, 95)), 4),
    }


def compute_hazard_iou(pred_hazard_mask: np.ndarray, target_hazard_mask: np.ndarray) -> float:
    """Computes Intersection over Union (IoU) for binary hazard maps."""
    p_bool = pred_hazard_mask.astype(bool)
    t_bool = target_hazard_mask.astype(bool)

    intersection = np.sum(np.logical_and(p_bool, t_bool))
    union = np.sum(np.logical_or(p_bool, t_bool))

    if union == 0:
        return 1.0
    return round(float(intersection / union), 4)


def compute_detection_precision_recall(
    pred_mask: np.ndarray,
    target_mask: np.ndarray,
) -> Dict[str, float]:
    """Computes precision, recall, and F1 score for detected hazards."""
    res = compute_confusion_matrix_and_rates(pred_mask, target_mask)
    return {
        "precision": res["precision"],
        "recall": res["recall_sensitivity"],
        "f1_score": res["f1_score"],
        "tp": res["confusion_matrix"]["true_positive_hazard"],
        "fp": res["confusion_matrix"]["false_positive_hazard"],
        "fn": res["confusion_matrix"]["false_negative_hazard"],
    }


def compute_image_reconstruction_metrics(pred_ortho: np.ndarray, target_ortho: np.ndarray) -> Dict[str, float]:
    """Computes PSNR (dB), SSIM, and MAE for super-resolved imagery."""
    p_norm = np.clip(pred_ortho.astype(np.float32), 0.0, 1.0)
    t_norm = np.clip(target_ortho.astype(np.float32), 0.0, 1.0)

    # Ensure identical shape
    if p_norm.shape != t_norm.shape:
        from scipy.ndimage import zoom
        zoom_factors = (t_norm.shape[0] / p_norm.shape[0], t_norm.shape[1] / p_norm.shape[1])
        p_norm = zoom(p_norm, zoom_factors, order=1)

    mae = float(np.mean(np.abs(p_norm - t_norm)))
    psnr_val = float(psnr_func(t_norm, p_norm, data_range=1.0))
    ssim_val = float(ssim_func(t_norm, p_norm, data_range=1.0))

    return {
        "psnr_db": round(psnr_val, 2),
        "ssim": round(ssim_val, 4),
        "ortho_mae": round(mae, 4),
    }
