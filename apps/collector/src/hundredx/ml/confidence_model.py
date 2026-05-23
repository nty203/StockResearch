"""LightGBM 기반 PPTR confidence model.

기존 pptr_confidence.py의 선형 합산을 교체.
- Monotonic constraints: 경제학적 prior를 모델에 강제 (BCR 오르면 confidence 오름 등)
- Isotonic calibration: raw probability → calibrated probability
- Walk-forward CV: 학습/검증 엄격 분리
- Fallback: 데이터 부족 시(sample < 100) 기존 선형 모델로 fallback

Usage:
  model = PPTRConfidenceModel()
  model.train(X_train, y_train)          # LightGBM 학습
  model.calibrate(X_val, y_val)          # Isotonic calibration
  conf = model.predict_proba(X_new)      # calibrated probability
  model.save("model_v1.pkl")
  model2 = PPTRConfidenceModel.load("model_v1.pkl")
"""
from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .feature_builder import FULL_FEATURE_NAMES, feature_names, features_to_array

logger = logging.getLogger(__name__)

# Monotone constraint: +1 = feature 증가→confidence 증가, -1 = 감소, 0 = 무제약
# FULL_FEATURE_NAMES 순서와 반드시 일치해야 함
_MONOTONE_CONSTRAINTS: dict[str, int] = {
    "bcr": 1,
    "backlog_yoy_pct": 1,
    "revenue_yoy_pct": 1,
    "opm_ttm": 1,
    "opm_delta": 1,
    "gross_margin_ttm": 1,
    "gross_margin_delta": 1,
    "roic": 1,
    "fcf_yield": 1,
    "revenue_qoq_acceleration": 1,
    "keyword_hits": 1,
    "keyword_density": 1,
    "amount_log": 1,
    "filing_count_90d": 1,
    "volume_spike_60d": 1,
    "above_ma20": 1,
    "above_ma60": 1,
    "above_ma200": 1,
    # refutation — 증가할수록 confidence 감소
    "dilution_yoy_pct": -1,
    "debt_ratio": -1,
    "ev_sales_growth_adj": -1,
    "backlog_quality_jump": -1,
    "goodwill_to_assets": -1,
    "composite_issuance": -1,
    "fingerprint_score": 1,
    "pptr_conditions_matched": 1,
    "timeline_stage": 1,
}


def _build_monotone_list() -> list[int]:
    """feature_names() 순서에 맞춘 monotone constraint list."""
    return [_MONOTONE_CONSTRAINTS.get(f, 0) for f in feature_names()]


@dataclass
class TrainingResult:
    n_train: int
    n_val: int
    brier_train: float
    brier_val: float
    auc_train: float
    auc_val: float
    best_iteration: int
    feature_importances: dict[str, float] = field(default_factory=dict)
    calibration_slope: float = 1.0
    trained_at: str = ""


class PPTRConfidenceModel:
    """LightGBM + Isotonic Calibration PPTR confidence 모델."""

    MIN_SAMPLES_FOR_ML = 100   # 이 미만이면 fallback
    MODEL_PATH_DEFAULT = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "models", "pptr_confidence.pkl"
    )

    def __init__(self) -> None:
        self._lgbm_model = None
        self._calibrator = None
        self._is_trained = False
        self._training_result: TrainingResult | None = None
        self._feature_names = feature_names()

    # ── Training ─────────────────────────────────────────────────────────

    def train(
        self,
        X_train: list[list[float]],
        y_train: list[int],
        X_val: list[list[float]] | None = None,
        y_val: list[int] | None = None,
        n_estimators: int = 500,
        learning_rate: float = 0.02,
        num_leaves: int = 15,
        early_stopping_rounds: int = 50,
    ) -> TrainingResult:
        """LightGBM 학습.

        Args:
            X_train: feature vectors (list of FULL_FEATURE_NAMES-sized lists)
            y_train: binary labels (1 = 10x in 24m, 0 = miss)
            X_val: validation features for early stopping
            y_val: validation labels
        """
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError(
                "lightgbm not installed. Run: uv add lightgbm"
            )

        if len(X_train) < self.MIN_SAMPLES_FOR_ML:
            logger.warning(
                "Only %d training samples — too few for LightGBM. "
                "Need ≥ %d. Using fallback.",
                len(X_train), self.MIN_SAMPLES_FOR_ML,
            )
            return TrainingResult(
                n_train=len(X_train), n_val=0,
                brier_train=0.25, brier_val=0.25,
                auc_train=0.5, auc_val=0.5,
                best_iteration=0,
            )

        import numpy as np
        X_tr = np.array(X_train, dtype=np.float32)
        y_tr = np.array(y_train, dtype=np.int32)

        # Positive class weight (class imbalance 보정 — winner는 rare)
        pos_count = int(y_tr.sum())
        neg_count = len(y_tr) - pos_count
        scale_pos_weight = neg_count / max(pos_count, 1)

        params = {
            "objective": "binary",
            "metric": ["binary_logloss", "auc"],
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "min_child_samples": max(20, len(X_train) // 100),
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "scale_pos_weight": scale_pos_weight,
            "monotone_constraints": _build_monotone_list(),
            "feature_name": self._feature_names,
            "verbose": -1,
            "n_jobs": -1,
            "random_state": 42,
        }

        callbacks = [lgb.log_evaluation(period=50), lgb.early_stopping(early_stopping_rounds)]
        eval_set = None
        if X_val is not None and y_val is not None:
            X_v = np.array(X_val, dtype=np.float32)
            y_v = np.array(y_val, dtype=np.int32)
            eval_set = [(X_v, y_v)]
        else:
            X_v = X_tr
            y_v = y_tr
            callbacks = [lgb.log_evaluation(period=100)]

        from lightgbm import LGBMClassifier
        model = LGBMClassifier(**params)
        model.fit(
            X_tr, y_tr,
            eval_set=eval_set or [(X_tr, y_tr)],
            callbacks=callbacks,
        )
        self._lgbm_model = model
        self._is_trained = True

        # Metrics
        from sklearn.metrics import roc_auc_score
        y_pred_train = model.predict_proba(X_tr)[:, 1]
        brier_train = float(np.mean((y_pred_train - y_tr) ** 2))
        auc_train = roc_auc_score(y_tr, y_pred_train) if len(set(y_tr)) > 1 else 0.5

        brier_val = brier_train
        auc_val = auc_train
        if X_val is not None and y_val is not None:
            y_pred_val = model.predict_proba(X_v)[:, 1]
            brier_val = float(np.mean((y_pred_val - y_v) ** 2))
            auc_val = roc_auc_score(y_v, y_pred_val) if len(set(y_v)) > 1 else 0.5

        # Feature importances
        importances = dict(zip(
            self._feature_names,
            [float(v) for v in model.feature_importances_],
        ))
        top_importances = dict(sorted(importances.items(), key=lambda x: -x[1])[:20])

        result = TrainingResult(
            n_train=len(X_train),
            n_val=len(X_val) if X_val else 0,
            brier_train=round(brier_train, 4),
            brier_val=round(brier_val, 4),
            auc_train=round(auc_train, 4),
            auc_val=round(auc_val, 4),
            best_iteration=model.best_iteration_ or n_estimators,
            feature_importances=top_importances,
            trained_at=datetime.now(timezone.utc).isoformat(),
        )
        self._training_result = result
        logger.info(
            "LightGBM trained: n=%d, Brier(train/val)=%.4f/%.4f, AUC=%.4f/%.4f, iter=%d",
            len(X_train), brier_train, brier_val, auc_train, auc_val, result.best_iteration,
        )
        return result

    def calibrate(
        self, X_val: list[list[float]], y_val: list[int]
    ) -> float:
        """Isotonic regression calibration on validation set.

        Returns Brier score after calibration.
        """
        if not self._is_trained or self._lgbm_model is None:
            raise RuntimeError("Model must be trained before calibration")
        try:
            from sklearn.calibration import CalibratedClassifierCV
            from sklearn.isotonic import IsotonicRegression
            import numpy as np
        except ImportError:
            raise ImportError("scikit-learn not installed. Run: uv add scikit-learn")

        X_v = np.array(X_val, dtype=np.float32)
        y_v = np.array(y_val, dtype=np.int32)

        # Get raw probabilities from LightGBM
        raw_probs = self._lgbm_model.predict_proba(X_v)[:, 1]

        # Fit isotonic regression: raw_probs → calibrated_probs
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(raw_probs, y_v)
        self._calibrator = iso

        # Brier score after calibration
        calibrated = iso.predict(raw_probs)
        brier = float(np.mean((calibrated - y_v) ** 2))
        logger.info("Calibration Brier score: %.4f (target ≤ 0.18)", brier)
        if brier > 0.25:
            logger.warning("Brier score %.4f is high — check data quality", brier)
        return brier

    # ── Inference ────────────────────────────────────────────────────────

    def predict_proba(self, X: list[list[float]] | list[float]) -> list[float]:
        """Calibrated confidence score [0.05, 0.95].

        Single sample: X = [f1, f2, ...] → returns [conf]
        Batch: X = [[...], [...]] → returns [conf1, conf2, ...]
        """
        if not self._is_trained:
            raise RuntimeError("Model not trained")

        import numpy as np
        # Normalize to 2D
        arr = np.array(X, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        raw_probs = self._lgbm_model.predict_proba(arr)[:, 1]

        if self._calibrator is not None:
            calibrated = self._calibrator.predict(raw_probs)
        else:
            calibrated = raw_probs

        # clamp [0.05, 0.95]
        clamped = [float(min(0.95, max(0.05, p))) for p in calibrated]
        return clamped

    def predict_single(
        self,
        stock_data: dict,
        filings: list[dict],
        match_meta: dict | None = None,
        category: str = "미분류",
    ) -> tuple[float, dict]:
        """stock_data + filings → (confidence, feature_dict).

        Fallback to linear model if LightGBM not trained.
        """
        from .feature_builder import build_feature_vector, features_to_array

        feat_dict = build_feature_vector(
            stock_data=stock_data,
            filings=filings,
            match_meta=match_meta,
            category=category,
        )
        feat_vec = features_to_array(feat_dict)

        if not self._is_trained:
            # Fallback to linear model
            from ..pptr_confidence import compute_pptr_confidence
            rule = {"category": category, "conditions": match_meta or {}}
            evidence = []
            conf, breakdown = compute_pptr_confidence(
                rule=rule,
                matched_conditions=(match_meta or {}).get("matched_conditions", []),
                evidence=evidence,
                stock_data=stock_data,
            )
            feat_dict["_fallback"] = 1.0
            return conf, feat_dict

        probs = self.predict_proba([feat_vec])
        return probs[0], feat_dict

    # ── Serialization ────────────────────────────────────────────────────

    def save(self, path: str | None = None) -> str:
        """모델 + calibrator → pickle 저장."""
        path = path or self.MODEL_PATH_DEFAULT
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "lgbm_model": self._lgbm_model,
            "calibrator": self._calibrator,
            "is_trained": self._is_trained,
            "training_result": self._training_result,
            "feature_names": self._feature_names,
            "version": "1.0",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        logger.info("Model saved to %s", path)
        return path

    @classmethod
    def load(cls, path: str | None = None) -> "PPTRConfidenceModel":
        """pickle에서 모델 로드."""
        path = path or cls.MODEL_PATH_DEFAULT
        if not os.path.exists(path):
            logger.warning("Model file not found at %s — returning untrained model", path)
            return cls()
        with open(path, "rb") as f:
            payload = pickle.load(f)
        model = cls()
        model._lgbm_model = payload.get("lgbm_model")
        model._calibrator = payload.get("calibrator")
        model._is_trained = payload.get("is_trained", False)
        model._training_result = payload.get("training_result")
        model._feature_names = payload.get("feature_names", feature_names())
        logger.info("Model loaded from %s", path)
        return model


# ── Singleton for production use ─────────────────────────────────────────────
_GLOBAL_MODEL: PPTRConfidenceModel | None = None


def get_model(auto_load: bool = True) -> PPTRConfidenceModel:
    """프로덕션용 singleton model. 첫 호출 시 디스크에서 로드."""
    global _GLOBAL_MODEL
    if _GLOBAL_MODEL is None:
        _GLOBAL_MODEL = PPTRConfidenceModel()
        if auto_load:
            _GLOBAL_MODEL = PPTRConfidenceModel.load()
    return _GLOBAL_MODEL


def train_and_save(client, model_path: str | None = None) -> TrainingResult:
    """DB에서 학습 데이터 로드 → LightGBM 학습 → calibration → 저장."""
    from .walk_forward import assert_no_test_leakage
    from ..data.survivorship_free import load_training_samples
    from .feature_builder import build_feature_vector, features_to_array

    logger.info("Loading training samples...")
    train_rows = load_training_samples(client, split="train")
    val_rows = load_training_samples(client, split="val")

    if not train_rows:
        logger.warning("No training data found. Run survivorship_free.build_survivorship_free_universe() first.")
        return TrainingResult(n_train=0, n_val=0, brier_train=0.25, brier_val=0.25,
                              auc_train=0.5, auc_val=0.5, best_iteration=0)

    # Leakage check
    assert_no_test_leakage(train_rows)

    logger.info("Building feature vectors (train=%d, val=%d)...", len(train_rows), len(val_rows))

    def _rows_to_XY(rows):
        X, y = [], []
        for r in rows:
            feat = build_feature_vector(
                stock_data=r,
                filings=[],
                match_meta={},
                category=r.get("category", "미분류"),
            )
            X.append(features_to_array(feat))
            y.append(int(r.get("label_10x_24m", 0)))
        return X, y

    X_train, y_train = _rows_to_XY(train_rows)
    X_val, y_val = _rows_to_XY(val_rows) if val_rows else (None, None)

    model = PPTRConfidenceModel()
    result = model.train(X_train, y_train, X_val, y_val)

    if X_val is not None:
        brier_cal = model.calibrate(X_val, y_val)
        result.brier_val = brier_cal

    path = model.save(model_path)
    logger.info("Model saved: %s", path)

    # Persist version to DB
    try:
        client.table("pptr_model_versions").insert({
            "version_tag": f"lgbm_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
            "model_path": path,
            "n_train": result.n_train,
            "n_val": result.n_val,
            "brier_val": result.brier_val,
            "auc_val": result.auc_val,
            "best_iteration": result.best_iteration,
            "feature_importances": result.feature_importances,
            "trained_at": result.trained_at,
        }).execute()
    except Exception as e:
        logger.warning("DB version save failed: %s", e)

    return result


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    from ...upsert import get_client

    parser = argparse.ArgumentParser(description="Train PPTR LightGBM model")
    parser.add_argument("--model-path", default=None)
    args = parser.parse_args()

    client = get_client()
    result = train_and_save(client, args.model_path)
    print(f"\n=== Training Complete ===")
    print(f"Samples: train={result.n_train}, val={result.n_val}")
    print(f"Brier: train={result.brier_train:.4f}, val={result.brier_val:.4f} (target ≤ 0.18)")
    print(f"AUC:   train={result.auc_train:.4f}, val={result.auc_val:.4f}")
    print(f"Best iteration: {result.best_iteration}")
    print(f"\nTop 10 features:")
    for feat, imp in sorted(result.feature_importances.items(), key=lambda x: -x[1])[:10]:
        print(f"  {feat:<35} {imp:.1f}")
