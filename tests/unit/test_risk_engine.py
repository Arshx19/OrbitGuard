"""Unit tests for app.core.risk_engine AI model & SHAP explainability."""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from app.core.risk_engine import CollisionRiskModel, RiskFeatures, RiskEngine


def test_risk_features_to_array():
    rf = RiskFeatures()
    rf.miss_distance = 0.42
    rf.relative_speed = 12.4
    rf.radial_velocity = -0.5
    rf.approach_angle = 88.5
    rf.time_to_tca = 4.2

    arr = rf.to_array()
    assert arr.shape == (1, 10)
    assert arr[0, 0] == 0.42
    assert arr[0, 1] == 12.4


def test_heuristic_risk_prediction():
    model = CollisionRiskModel()
    rf = RiskFeatures()
    rf.miss_distance = 0.42
    rf.relative_speed = 12.4
    rf.radial_velocity = -1.2
    rf.time_to_tca = 2.0

    prob, level = model.predict_risk(rf)
    assert prob > 0.6
    assert level in ['high', 'critical']


def test_model_training_and_shap_explainability():
    # Generate synthetic training dataset (X: 10 features, y: binary risk label)
    np.random.seed(42)
    n_samples = 100
    X = np.random.rand(n_samples, 10)
    
    # Feature 0 is miss_distance (small = high risk)
    # Feature 1 is relative_speed (high = high risk)
    X[:, 0] = np.random.uniform(0.1, 20.0, n_samples)
    X[:, 1] = np.random.uniform(0.5, 15.0, n_samples)
    y = ((X[:, 0] < 2.0) & (X[:, 1] > 8.0)).astype(int)

    model = CollisionRiskModel()
    model.train_model(X, y)
    assert model.is_trained is True

    # Test prediction on a high-risk sample
    rf = RiskFeatures()
    rf.miss_distance = 0.3
    rf.relative_speed = 14.0
    prob, level = model.predict_risk(rf)
    assert prob >= 0.0

    # Test SHAP explanation output
    explanation = model.explain_prediction(rf)
    assert 'shap_values' in explanation
    assert 'miss_distance_km' in explanation['shap_values']
