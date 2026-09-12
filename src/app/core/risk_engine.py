"""
Risk assessment module for ORBITGUARD AI.
Calculates collision risk probabilities and provides explainability using ML models and SHAP.
"""

import logging
import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Union
from datetime import datetime
import pickle
import os

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import shap

logger = logging.getLogger(__name__)


class RiskFeatures:
    """Container for risk assessment features."""

    def __init__(self):
        self.miss_distance: Optional[float] = None  # km
        self.relative_speed: Optional[float] = None  # km/s
        self.radial_velocity: Optional[float] = None  # km/s (negative = approaching)
        self.tangential_speed: Optional[float] = None  # km/s
        self.approach_angle: Optional[float] = None  # degrees
        self.time_to_tca: Optional[float] = None  # hours until TCA
        self.satellite_size_factor: Optional[float] = None  # Combined size/risk factor
        self.orbital_altitude: Optional[float] = None  # km
        self.orbital_inclination: Optional[float] = None  # degrees
        self.space_weather_factor: Optional[float] = None  # Based on KP-index, etc.

        # Derived features
        self.collision_probability: Optional[float] = None
        self.risk_level: Optional[str] = None  # 'low', 'medium', 'high', 'critical'

    def to_array(self) -> np.ndarray:
        """Convert features to numpy array for ML model input."""
        # Handle missing values
        features = [
            self.miss_distance if self.miss_distance is not None else 999.0,
            self.relative_speed if self.relative_speed is not None else 0.0,
            abs(self.radial_velocity) if self.radial_velocity is not None else 0.0,
            self.tangential_speed if self.tangential_speed is not None else 0.0,
            self.approach_angle if self.approach_angle is not None else 90.0,
            self.time_to_tca if self.time_to_tca is not None else 999.0,
            self.satellite_size_factor if self.satellite_size_factor is not None else 1.0,
            self.orbital_altitude if self.orbital_altitude is not None else 500.0,
            self.orbital_inclination if self.orbital_inclination is not None else 0.0,
            self.space_weather_factor if self.space_weather_factor is not None else 1.0
        ]
        return np.array(features).reshape(1, -1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert features to dictionary."""
        return {
            'miss_distance_km': self.miss_distance,
            'relative_speed_kms': self.relative_speed,
            'radial_velocity_kms': self.radial_velocity,
            'tangential_speed_kms': self.tangential_speed,
            'approach_angle_degrees': self.approach_angle,
            'time_to_tca_hours': self.time_to_tca,
            'satellite_size_factor': self.satellite_size_factor,
            'orbital_altitude_km': self.orbital_altitude,
            'orbital_inclination_degrees': self.orbital_inclination,
            'space_weather_factor': self.space_weather_factor,
            'collision_probability': self.collision_probability,
            'risk_level': self.risk_level
        }


class CollisionRiskModel:
    """Machine learning model for collision risk assessment."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize risk model.

        Args:
            model_path: Path to pre-trained model file (optional)
        """
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_names = [
            'miss_distance_km', 'relative_speed_kms', 'radial_velocity_kms',
            'tangential_speed_kms', 'approach_angle_degrees', 'time_to_tca_hours',
            'satellite_size_factor', 'orbital_altitude_km', 'orbital_inclination_degrees',
            'space_weather_factor'
        ]
        self.logger = logging.getLogger(__name__)

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def train_model(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train the risk assessment model.

        Args:
            X: Feature matrix of shape (n_samples, n_features)
            y: Binary labels (0 = safe, 1 = collision risk)
        """
        try:
            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            self.model.fit(X_scaled, y)
            self.is_trained = True

            self.logger.info(f"Risk model trained on {X.shape[0]} samples with {X.shape[1]} features")
            self.logger.info(f"Feature importances: {dict(zip(self.feature_names, self.model.feature_importances_))}")

        except Exception as e:
            self.logger.error(f"Error training risk model: {e}")
            raise

    def predict_risk(self, features: RiskFeatures) -> Tuple[float, str]:
        """
        Predict collision risk probability and risk level.

        Args:
            features: RiskFeatures object containing assessment data

        Returns:
            Tuple of (collision_probability, risk_level)
        """
        if not self.is_trained:
            self.logger.warning("Model not trained, using heuristic risk assessment")
            return self._heuristic_risk_assessment(features)

        try:
            # Prepare features
            X = features.to_array()
            X_scaled = self.scaler.transform(X)

            # Get prediction probabilities
            probabilities = self.model.predict_proba(X_scaled)[0]
            collision_probability = float(probabilities[1])  # Probability of class 1 (risk)

            # Determine risk level based on probability thresholds
            if collision_probability < 0.1:
                risk_level = 'low'
            elif collision_probability < 0.3:
                risk_level = 'medium'
            elif collision_probability < 0.7:
                risk_level = 'high'
            else:
                risk_level = 'critical'

            return collision_probability, risk_level

        except Exception as e:
            self.logger.error(f"Error in risk prediction: {e}")
            return self._heuristic_risk_assessment(features)

    def _heuristic_risk_assessment(self, features: RiskFeatures) -> Tuple[float, str]:
        """
        Fallback heuristic risk assessment when ML model is not available.

        Args:
            features: RiskFeatures object

        Returns:
            Tuple of (collision_probability, risk_level)
        """
        # Simple heuristic based on miss distance and relative speed
        miss_distance = features.miss_distance or 999.0
        relative_speed = features.relative_speed or 0.0
        radial_velocity = abs(features.radial_velocity or 0.0)

        # Base risk inversely proportional to miss distance
        distance_risk = max(0, min(1, (10.0 - miss_distance) / 10.0))  # 0-10 km range

        # Speed risk increases with relative speed
        speed_risk = min(1, relative_speed / 20.0)  # Normalize by 20 km/s

        # Approach risk (head-on is worse)
        approach_risk = min(1, radial_velocity / 10.0) if radial_velocity > 0 else 0.0

        # Combined risk score
        risk_score = (distance_risk * 0.5 + speed_risk * 0.3 + approach_risk * 0.2)
        risk_score = max(0, min(1, risk_score))  # Clamp to 0-1

        # Convert to risk level
        if risk_score < 0.1:
            risk_level = 'low'
        elif risk_score < 0.3:
            risk_level = 'medium'
        elif risk_score < 0.7:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        return float(risk_score), risk_level

    def explain_prediction(self, features: RiskFeatures) -> Dict[str, Any]:
        """
        Generate SHAP explanation for risk prediction.

        Args:
            features: RiskFeatures object to explain

        Returns:
            Dictionary containing SHAP values and explanation data
        """
        if not self.is_trained:
            self.logger.warning("Model not trained, cannot provide SHAP explanation")
            return {'error': 'Model not trained'}

        try:
            # Prepare features
            X = features.to_array()
            X_scaled = self.scaler.transform(X)

            # Create SHAP explainer
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X_scaled)

            # Get expected value and shap values for class 1 (risk)
            expected_value = explainer.expected_value[1] if isinstance(explainer.expected_value, list) else explainer.expected_value
            shap_vals = shap_values[1] if isinstance(shap_values, list) else shap_values

            # Create explanation dictionary
            explanation = {
                'expected_value': float(expected_value),
                'shap_values': dict(zip(self.feature_names, shap_vals[0].tolist())),
                'feature_values': dict(zip(self.feature_names, X[0].tolist())),
                'prediction_probability': float(self.model.predict_proba(X_scaled)[0][1])
            }

            return explanation

        except Exception as e:
            self.logger.error(f"Error generating SHAP explanation: {e}")
            return {'error': str(e)}

    def save_model(self, filepath: str) -> None:
        """
        Save trained model to file.

        Args:
            filepath: Path to save model
        """
        if not self.is_trained:
            self.logger.warning("Cannot save untrained model")
            return

        try:
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'is_trained': self.is_trained
            }
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            self.logger.info(f"Model saved to {filepath}")
        except Exception as e:
            self.logger.error(f"Error saving model: {e}")

    def load_model(self, filepath: str) -> None:
        """
        Load trained model from file.

        Args:
            filepath: Path to load model from
        """
        try
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)

            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.is_trained = model_data['is_trained']

            self.logger.info(f"Model loaded from {filepath}")
        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            # Reset to default state
            self.__init__()


class RiskEngine:
    """Main risk assessment engine for ORBITGUARD AI."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize risk engine.

        Args:
            model_path: Path to pre-trained risk model (optional)
        """
        self.collision_model = CollisionRiskModel(model_path)
        self.logger = logging.getLogger(__name__)

    def assess_conjunction_risk(
        self,
        conjunction_result,
        satellite1_params: Optional[Dict[str, Any]] = None,
        satellite2_params: Optional[Dict[str, Any]] = None
    ) -> RiskFeatures:
        """
        Assess risk for a detected conjunction.

        Args:
            conjunction_result: ConjunctionResult object from conjunction detection
            satellite1_params: Parameters for satellite 1 (size, altitude, etc.)
            satellite2_params: Parameters for satellite 2 (size, altitude, etc.)

        Returns:
            RiskFeatures object with risk assessment
        """
        features = RiskFeatures()

        # Extract basic conjunction data
        features.miss_distance = conjunction_result.miss_distance
        features.time_to_tca = None  # Would need current time to calculate

        # Calculate conjunction geometry if velocities available
        if (conjunction_result.velocity1 is not None and
            conjunction_result.velocity2 is not None and
            conjunction_result.position1 is not None and
            conjunction_result.position2 is not None):

            geometry = self._calculate_conjunction_geometry(
                conjunction_result.position1,
                conjunction_result.position2,
                conjunction_result.velocity1,
                conjunction_result.velocity2
            )

            features.relative_speed = geometry.get('relative_speed_kms')
            features.radial_velocity = geometry.get('radial_velocity_kms')
            features.tangential_speed = geometry.get('tangential_speed_kms')
            features.approach_angle = geometry.get('approach_angle_degrees')

        # Estimate satellite parameters if not provided
        if satellite1_params is None:
            satellite1_params = self._estimate_satellite_params(conjunction_result.satellite1_id)
        if satellite2_params is None:
            satellite2_params = self._estimate_satellite_params(conjunction_result.satellite2_id)

        # Calculate combined satellite size factor
        size1 = satellite1_params.get('size_m2', 10.0)  # Default 10 m²
        size2 = satellite2_params.get('size_m2', 10.0)
        features.satellite_size_factor = np.sqrt(size1 * size2) / 10.0  # Normalize

        # Calculate average orbital altitude
        alt1 = satellite1_params.get('altitude_km', 500.0)
        alt2 = satellite2_params.get('altitude_km', 500.0)
        features.orbital_altitude = (alt1 + alt2) / 2.0

        # Calculate average inclination
        inc1 = satellite1_params.get('inclination_deg', 0.0)
        inc2 = satellite2_params.get('inclination_deg', 0.0)
        features.orbital_inclination = abs(inc1 - inc2) / 2.0  # Relative inclination

        # Space weather factor (simplified - would use real KP-index data in production)
        features.space_weather_factor = 1.0  # Nominal conditions

        # Assess risk using ML model
        collision_probability, risk_level = self.collision_model.predict_risk(features)
        features.collision_probability = collision_probability
        features.risk_level = risk_level

        self.logger.info(
            f"Risk assessment for conjunction {conjunction_result.satellite1_id}-{conjunction_result.satellite2_id}: "
            f"P(collision)={collision_probability:.4f}, Level={risk_level}"
        )

        return features

    def _calculate_conjunction_geometry(
        self,
        position1: np.ndarray,
        position2: np.ndarray,
        velocity1: np.ndarray,
        velocity2: np.ndarray
    ) -> Dict[str, Any]:
        """Calculate conjunction geometry from state vectors."""
        # Miss distance vector (from sat2 to sat1)
        miss_vector = position1 - position2
        miss_distance = np.linalg.norm(miss_vector)
        miss_unit_vector = miss_vector / miss_distance if miss_distance > 0 else np.zeros(3)

        # Relative velocity
        relative_velocity = velocity1 - velocity2
        relative_speed = np.linalg.norm(relative_velocity)

        # Radial velocity component (negative = approaching)
        radial_velocity = np.dot(relative_velocity, miss_unit_vector)

        # Tangential velocity
        tangential_velocity = relative_velocity - radial_velocity * miss_unit_vector
        tangential_speed = np.linalg.norm(tangential_velocity)

        # Approach angle
        if relative_speed > 0 and miss_distance > 0:
            approach_angle = np.degrees(np.arccos(
                np.clip(np.dot(relative_velocity, miss_vector) / (relative_speed * miss_distance), -1, 1)
            ))
        else:
            approach_angle = 0.0

        return {
            'miss_distance_km': float(miss_distance),
            'relative_speed_kms': float(relative_speed),
            'radial_velocity_kms': float(radial_velocity),
            'tangential_speed_kms': float(tangential_speed),
            'approach_angle_degrees': float(approach_angle),
            'is_approaching': radial_velocity < 0
        }

    def _estimate_satellite_params(self, satellite_id: int) -> Dict[str, Any]:
        """
        Estimate satellite parameters based on ID or catalog data.
        In production, this would query a satellite catalog database.
        """
        # Simple estimation based on ID ranges (for demonstration)
        # In reality, this would look up actual satellite characteristics

        # Default parameters
        params = {
            'size_m2': 10.0,          # Cross-sectional area in m²
            'altitude_km': 500.0,     # Orbital altitude in km
            'inclination_deg': 0.0,   # Orbital inclination in degrees
            'mass_kg': 1000.0         # Mass in kg
        }

        # Adjust based on satellite ID ranges (crude estimation)
        if satellite_id < 1000:
            # Early satellites - tend to be larger
            params['size_m2'] = 50.0
            params['mass_kg'] = 5000.0
        elif satellite_id < 5000:
            # Middle era - moderate size
            params['size_m2'] = 20.0
            params['mass_kg'] = 2000.0
        else:
            # Modern satellites - includes many small CubeSats
            if satellite_id % 100 < 20:  # Assume 20% are CubeSats
                params['size_m2'] = 0.1   # 1U CubeSat
                params['mass_kg'] = 1.0
            else:
                params['size_m2'] = 10.0
                params['mass_kg'] = 1000.0

        # Estimate altitude based on ID (very rough)
        params['altitude_km'] = 400.0 + (satellite_id % 20) * 10.0  # 400-600 km range
        params['inclination_deg'] = satellite_id % 180  # 0-180 degrees

        return params

    def generate_risk_report(
        self,
        conjunction_result,
        risk_features: RiskFeatures
    ) -> Dict[str, Any]:
        """
        Generate comprehensive risk report for a conjunction.

        Args:
            conjunction_result: ConjunctionResult object
            risk_features: RiskFeatures object from assessment

        Returns:
            Dictionary containing complete risk report
        """
        report = {
            'conjunction': {
                'satellite1_id': conjunction_result.satellite1_id,
                'satellite2_id': conjunction_result.satellite2_id,
                'tca': conjunction_result.tca.isoformat() if conjunction_result.tca else None,
                'miss_distance_km': conjunction_result.miss_distance,
                'geometry': self._calculate_conjunction_geometry(
                    conjunction_result.position1 or np.zeros(3),
                    conjunction_result.position2 or np.zeros(3),
                    conjunction_result.velocity1 or np.zeros(3),
                    conjunction_result.velocity2 or np.zeros(3)
                ) if all(v is not None for v in [
                    conjunction_result.position1, conjunction_result.position2,
                    conjunction_result.velocity1, conjunction_result.velocity2
                ]) else None
            },
            'risk_assessment': risk_features.to_dict(),
            'explanation': None,
            'recommendations': self._generate_recommendations(risk_features)
        }

        # Add SHAP explanation if model is trained
        if self.collision_model.is_trained:
            report['explanation'] = self.collision_model.explain_prediction(risk_features)

        return report

    def _generate_recommendations(self, features: RiskFeatures) -> List[str]:
        """
        Generate mitigation recommendations based on risk level.

        Args:
            features: RiskFeatures object

        Returns:
            List of recommendation strings
        """
        recommendations = []
        risk_level = features.risk_level or 'unknown'
        miss_distance = features.miss_distance or 999.0
        collision_prob = features.collision_probability or 0.0

        if risk_level == 'low':
            recommendations.append("Continue normal operations")
            recommendations.append("Monitor conjunction for any changes")
        elif risk_level == 'medium':
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Prepare for possible collision avoidance maneuver")
            recommendations.append("Verify satellite tracking data accuracy")
        elif risk_level == 'high':
            recommendations.append("Consider collision避让 maneuver")
            recommendations.append("Notify satellite operators of both objects")
            recommendations.append("Prepare conjunction data summary for decision makers")
            if miss_distance < 1.0:
                recommendations.append("URGENT: Miss distance < 1km - immediate action may be required")
        elif risk_level == 'critical':
            recommendations.append("IMMEDIATE ACTION REQUIRED")
            recommendations.append("Execute collision避让 maneuver if possible")
            recommendations.append("Issue emergency notifications to all affected parties")
            recommendations.append("Consider safing procedures for vulnerable satellites")
            recommendations.append("Prepare post-conjunction assessment plans")

        # Add specific recommendations based on factors
        if collision_prob > 0.5:
            recommendations.append(f"High collision probability ({collision_prob:.1%}) warrants serious consideration of避让")

        if features.relative_speed and features.relative_speed > 15.0:
            recommendations.append("High relative velocity increases collision energy -避让 effectiveness may be reduced")

        if features.time_to_tca and features.time_to_tca < 1.0:
            recommendations.append("TCA imminent (< 1 hour) - limited time for避让 decision")

        return recommendations


def create_sample_risk_model() -> CollisionRiskModel:
    """
    Create and train a sample risk model for demonstration purposes.
    In production, this would be replaced with a properly trained model.

    Returns:
        Trained CollisionRiskModel instance
    """
    model = CollisionRiskModel()

    # Generate synthetic training data for demonstration
    np.random.seed(42)
    n_samples = 1000

    # Features: [miss_distance, relative_speed, radial_velocity, tangential_speed,
    #           approach_angle, time_to_tca, satellite_size, altitude, inclination, space_weather]
    X = np.random.rand(n_samples, 10)

    # Scale features to realistic ranges
    X[:, 0] = X[:, 0] * 20.0          # miss_distance: 0-20 km
    X[:, 1] = X[:, 1] * 20.0          # relative_speed: 0-20 km/s
    X[:, 2] = (X[:, 2] - 0.5) * 10.0  # radial_velocity: -5 to 5 km/s
    X[:, 3] = X[:, 3] * 10.0          # tangential_speed: 0-10 km/s
    X[:, 4] = X[:, 4] * 180.0         # approach_angle: 0-180 degrees
    X[:, 5] = X[:, 5] * 48.0          # time_to_tca: 0-48 hours
    X[:, 6] = X[:, 6] * 100.0         # satellite_size_factor: 0-100
    X[:, 7] = X[:, 7] * 1000.0        # altitude: 0-1000 km
    X[:, 8] = X[:, 8] * 180.0         # inclination: 0-180 degrees
    X[:, 9] = X[:, 9] * 3.0 + 0.5     # space_weather: 0.5-3.5

    # Generate labels based on heuristic: close distance + high speed + approaching = higher risk
    risk_score = (
        np.maximum(0, (10.0 - X[:, 0]) / 10.0) * 0.4 +  # Close distance
        np.minimum(1, X[:, 1] / 15.0) * 0.3 +             # High speed
        np.maximum(0, X[:, 2]) / 10.0 * 0.2 +             # Approaching (negative radial vel)
        np.minimum(1, (180.0 - X[:, 4]) / 90.0) * 0.1     # Head-on angle
    )
    y = (risk_score > 0.3).astype(int)  # Binary label

    # Train model
    model.train_model(X, y)

    return model


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Create and test risk engine
    risk_engine = RiskEngine()

    # Train sample model if not already trained
    if not risk_engine.collision_model.is_trained:
        logger.info("Training sample risk model...")
        risk_engine.collision_model = create_sample_risk_model()

    logger.info("Risk engine ready for use")