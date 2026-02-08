"""
Feature Store for Trading ML Models

Centralized feature management system:
- Feature definitions with metadata
- Feature versioning
- Feature computation pipelines
- Feature serving (offline and online)
- Feature lineage tracking
"""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features"""

    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    BINARY = "binary"
    TEMPORAL = "temporal"
    TEXT = "text"
    EMBEDDING = "embedding"


class ComputationMode(Enum):
    """Feature computation modes"""

    BATCH = "batch"  # Compute in batch
    STREAMING = "streaming"  # Compute in real-time
    ON_DEMAND = "on_demand"  # Compute when requested


@dataclass
class FeatureDefinition:
    """Definition of a single feature"""

    name: str
    description: str
    feature_type: FeatureType
    computation_mode: ComputationMode = ComputationMode.BATCH

    # Data properties
    dtype: str = "float32"
    default_value: Any = None
    nullable: bool = False

    # Computation
    dependencies: list[str] = field(default_factory=list)  # Other features
    computation_fn: str | None = None  # Function name/code
    parameters: dict[str, Any] = field(default_factory=dict)

    # Statistics (populated during training)
    mean: float | None = None
    std: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    unique_values: list[Any] | None = None

    # Metadata
    owner: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "feature_type": self.feature_type.value,
            "computation_mode": self.computation_mode.value,
            "dtype": self.dtype,
            "default_value": self.default_value,
            "nullable": self.nullable,
            "dependencies": self.dependencies,
            "computation_fn": self.computation_fn,
            "parameters": self.parameters,
            "mean": self.mean,
            "std": self.std,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "unique_values": self.unique_values,
            "owner": self.owner,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureDefinition":
        """Create from dictionary"""
        data = data.copy()
        data["feature_type"] = FeatureType(data["feature_type"])
        data["computation_mode"] = ComputationMode(data["computation_mode"])
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class FeatureGroup:
    """A group of related features"""

    name: str
    description: str
    features: list[str]  # Feature names

    # Entity info (what the features describe)
    entity_type: str = "trade"  # "trade", "candle", "order", etc.
    entity_id_column: str = "id"
    timestamp_column: str = "timestamp"

    # Computation
    source_table: str = ""
    refresh_interval_seconds: int = 300

    # Metadata
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "features": self.features,
            "entity_type": self.entity_type,
            "entity_id_column": self.entity_id_column,
            "timestamp_column": self.timestamp_column,
            "source_table": self.source_table,
            "refresh_interval_seconds": self.refresh_interval_seconds,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class FeatureVersion:
    """A versioned snapshot of feature definitions"""

    version: str
    created_at: datetime
    feature_definitions: dict[str, FeatureDefinition]
    feature_groups: dict[str, FeatureGroup]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "feature_count": len(self.feature_definitions),
            "group_count": len(self.feature_groups),
        }


class FeatureStore:
    """
    Centralized Feature Store for Trading ML

    Example:
        store = FeatureStore()

        # Define a feature
        store.register_feature(FeatureDefinition(
            name="rsi_14",
            description="14-period RSI",
            feature_type=FeatureType.NUMERICAL,
            computation_fn="compute_rsi",
            parameters={"period": 14}
        ))

        # Create feature group
        store.create_group(FeatureGroup(
            name="momentum_indicators",
            features=["rsi_14", "macd", "stochastic"]
        ))

        # Compute features
        features = await store.compute(data, group="momentum_indicators")
    """

    def __init__(self, storage_path: str = "./feature_store"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self.features: dict[str, FeatureDefinition] = {}
        self.groups: dict[str, FeatureGroup] = {}
        self.versions: dict[str, FeatureVersion] = {}

        # Computation functions registry
        self.computation_registry: dict[str, Callable] = {}

        # Cache
        self.feature_cache: dict[str, np.ndarray] = {}
        self.cache_timestamps: dict[str, datetime] = {}

        # Load existing definitions
        self._load_store()

        # Register built-in computations
        self._register_builtin_computations()

    def _load_store(self) -> None:
        """Load feature store from disk"""
        index_path = self.storage_path / "store_index.json"

        if index_path.exists():
            try:
                with open(index_path) as f:
                    data = json.load(f)

                for name, feat_data in data.get("features", {}).items():
                    self.features[name] = FeatureDefinition.from_dict(feat_data)

                for name, group_data in data.get("groups", {}).items():
                    group_data["created_at"] = datetime.fromisoformat(group_data["created_at"])
                    self.groups[name] = FeatureGroup(**group_data)

                logger.info(f"Loaded {len(self.features)} features, {len(self.groups)} groups")
            except Exception as e:
                logger.error(f"Failed to load feature store: {e}")

    def _save_store(self) -> None:
        """Save feature store to disk"""
        index_path = self.storage_path / "store_index.json"

        data = {
            "features": {name: feat.to_dict() for name, feat in self.features.items()},
            "groups": {name: group.to_dict() for name, group in self.groups.items()},
            "updated_at": datetime.now(UTC).isoformat(),
        }

        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)

    def _register_builtin_computations(self) -> None:
        """Register built-in feature computation functions"""

        def compute_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
            """Compute RSI"""
            deltas = np.diff(data)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.zeros(len(data))
            avg_loss = np.zeros(len(data))

            avg_gain[period] = np.mean(gains[:period])
            avg_loss[period] = np.mean(losses[:period])

            for i in range(period + 1, len(data)):
                avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
                avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

            rs = np.divide(avg_gain, avg_loss, where=avg_loss != 0)
            rsi = 100 - (100 / (1 + rs))
            rsi[:period] = 50  # Fill initial values

            return rsi

        def compute_sma(data: np.ndarray, period: int = 20) -> np.ndarray:
            """Compute Simple Moving Average"""
            result = np.zeros(len(data))
            for i in range(period - 1, len(data)):
                result[i] = np.mean(data[i - period + 1 : i + 1])
            result[: period - 1] = data[: period - 1]
            return result

        def compute_ema(data: np.ndarray, period: int = 20) -> np.ndarray:
            """Compute Exponential Moving Average"""
            alpha = 2 / (period + 1)
            result = np.zeros(len(data))
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
            return result

        def compute_macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> np.ndarray:
            """Compute MACD"""
            ema_fast = compute_ema(data, fast)
            ema_slow = compute_ema(data, slow)
            macd_line = ema_fast - ema_slow
            return macd_line

        def compute_bollinger(data: np.ndarray, period: int = 20, std_dev: float = 2.0) -> np.ndarray:
            """Compute Bollinger Band width"""
            sma = compute_sma(data, period)
            rolling_std = np.zeros(len(data))
            for i in range(period - 1, len(data)):
                rolling_std[i] = np.std(data[i - period + 1 : i + 1])
            bb_width = (std_dev * 2 * rolling_std) / (sma + 1e-10)
            return bb_width

        def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
            """Compute Average True Range"""
            tr = np.maximum(
                high - low,
                np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))),
            )
            tr[0] = high[0] - low[0]
            return compute_ema(tr, period)

        def compute_returns(data: np.ndarray, period: int = 1) -> np.ndarray:
            """Compute returns"""
            returns = np.zeros(len(data))
            returns[period:] = (data[period:] - data[:-period]) / (data[:-period] + 1e-10)
            return returns

        def compute_volatility(data: np.ndarray, period: int = 20) -> np.ndarray:
            """Compute rolling volatility"""
            returns = compute_returns(data)
            volatility = np.zeros(len(data))
            for i in range(period - 1, len(data)):
                volatility[i] = np.std(returns[i - period + 1 : i + 1])
            return volatility

        def compute_momentum(data: np.ndarray, period: int = 10) -> np.ndarray:
            """Compute momentum"""
            momentum = np.zeros(len(data))
            momentum[period:] = data[period:] - data[:-period]
            return momentum

        # Register all
        self.computation_registry.update(
            {
                "compute_rsi": compute_rsi,
                "compute_sma": compute_sma,
                "compute_ema": compute_ema,
                "compute_macd": compute_macd,
                "compute_bollinger": compute_bollinger,
                "compute_atr": compute_atr,
                "compute_returns": compute_returns,
                "compute_volatility": compute_volatility,
                "compute_momentum": compute_momentum,
            }
        )

    def register_computation(self, name: str, fn: Callable) -> None:
        """Register a custom computation function"""
        self.computation_registry[name] = fn
        logger.info(f"Registered computation: {name}")

    def register_feature(self, feature: FeatureDefinition, update_if_exists: bool = True) -> None:
        """
        Register a feature definition

        Args:
            feature: Feature definition
            update_if_exists: Whether to update if feature already exists
        """
        if feature.name in self.features and not update_if_exists:
            raise ValueError(f"Feature {feature.name} already exists")

        self.features[feature.name] = feature
        self._save_store()

        logger.info(f"Registered feature: {feature.name}")

    def create_group(self, group: FeatureGroup) -> None:
        """Create a feature group"""
        # Validate all features exist
        for feat_name in group.features:
            if feat_name not in self.features:
                raise ValueError(f"Feature {feat_name} not found")

        self.groups[group.name] = group
        self._save_store()

        logger.info(f"Created group: {group.name} with {len(group.features)} features")

    def get_feature(self, name: str) -> FeatureDefinition | None:
        """Get feature definition by name"""
        return self.features.get(name)

    def get_group(self, name: str) -> FeatureGroup | None:
        """Get feature group by name"""
        return self.groups.get(name)

    def list_features(
        self,
        tags: list[str] | None = None,
        feature_type: FeatureType | None = None,
    ) -> list[FeatureDefinition]:
        """List features with optional filtering"""
        result = list(self.features.values())

        if tags:
            result = [f for f in result if any(t in f.tags for t in tags)]

        if feature_type:
            result = [f for f in result if f.feature_type == feature_type]

        return result

    def list_groups(self) -> list[FeatureGroup]:
        """List all feature groups"""
        return list(self.groups.values())

    async def compute(
        self,
        data: dict[str, np.ndarray],
        features: list[str] | None = None,
        group: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, np.ndarray]:
        """
        Compute features from input data

        Args:
            data: Input data dict (column_name -> values)
            features: List of feature names to compute
            group: Name of feature group to compute
            use_cache: Whether to use cached values

        Returns:
            Dict of feature_name -> computed values
        """
        # Get feature list
        if group:
            if group not in self.groups:
                raise ValueError(f"Group {group} not found")
            feature_list = self.groups[group].features
        elif features:
            feature_list = features
        else:
            feature_list = list(self.features.keys())

        results = {}

        for feat_name in feature_list:
            feat_def = self.features.get(feat_name)
            if feat_def is None:
                logger.warning(f"Feature {feat_name} not found, skipping")
                continue

            # Check cache
            cache_key = self._get_cache_key(feat_name, data)
            if use_cache and cache_key in self.feature_cache:
                results[feat_name] = self.feature_cache[cache_key]
                continue

            # Compute feature
            try:
                computed = await self._compute_single(feat_def, data, results)
                results[feat_name] = computed

                # Cache result
                self.feature_cache[cache_key] = computed
                self.cache_timestamps[cache_key] = datetime.now(UTC)

            except Exception as e:
                logger.error(f"Failed to compute {feat_name}: {e}")
                if feat_def.default_value is not None:
                    n_samples = len(next(iter(data.values())))
                    results[feat_name] = np.full(n_samples, feat_def.default_value)

        return results

    async def _compute_single(
        self,
        feature: FeatureDefinition,
        data: dict[str, np.ndarray],
        already_computed: dict[str, np.ndarray],
    ) -> np.ndarray:
        """Compute a single feature"""
        # Check dependencies
        for dep in feature.dependencies:
            if dep not in already_computed and dep not in data:
                dep_def = self.features.get(dep)
                if dep_def:
                    already_computed[dep] = await self._compute_single(dep_def, data, already_computed)

        # Get computation function
        if feature.computation_fn is None:
            raise ValueError(f"No computation function for {feature.name}")

        fn = self.computation_registry.get(feature.computation_fn)
        if fn is None:
            raise ValueError(f"Computation function {feature.computation_fn} not found")

        # Prepare input data
        # Try to get data from already computed or raw data
        input_data = {**data, **already_computed}

        # Call computation function with parameters
        params = feature.parameters.copy()

        # Handle different function signatures
        import inspect

        sig = inspect.signature(fn)

        if len(sig.parameters) == 1:
            # Simple function with just data
            result = fn(
                input_data.get("close", input_data.get(list(input_data.keys())[0])),
                **params,
            )
        else:
            # Function that expects multiple columns
            result = fn(
                **{k: input_data[k] for k in sig.parameters if k in input_data},
                **params,
            )

        return result

    def _get_cache_key(self, feature_name: str, data: dict[str, np.ndarray]) -> str:
        """Generate cache key for feature computation using SHA256"""
        # Hash based on feature name and data shape/sample
        data_hash = hashlib.sha256()
        for k, v in sorted(data.items()):
            data_hash.update(k.encode())
            data_hash.update(str(v.shape).encode())
            if len(v) > 0:
                data_hash.update(str(v[0]).encode())
                data_hash.update(str(v[-1]).encode())

        return f"{feature_name}_{data_hash.hexdigest()[:16]}"

    def clear_cache(self, feature_name: str | None = None, older_than: datetime | None = None) -> int:
        """
        Clear feature cache

        Args:
            feature_name: Clear only this feature's cache
            older_than: Clear cache entries older than this

        Returns:
            Number of entries cleared
        """
        cleared = 0

        keys_to_delete = []

        for key in self.feature_cache:
            if feature_name and not key.startswith(feature_name):
                continue

            if older_than:
                cache_time = self.cache_timestamps.get(key)
                if cache_time and cache_time >= older_than:
                    continue

            keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.feature_cache[key]
            if key in self.cache_timestamps:
                del self.cache_timestamps[key]
            cleared += 1

        logger.info(f"Cleared {cleared} cache entries")
        return cleared

    def update_statistics(self, feature_name: str, values: np.ndarray) -> None:
        """
        Update feature statistics from data

        Args:
            feature_name: Feature to update
            values: Computed feature values
        """
        if feature_name not in self.features:
            return

        feat = self.features[feature_name]

        values = values[~np.isnan(values)]

        if len(values) == 0:
            return

        feat.mean = float(np.mean(values))
        feat.std = float(np.std(values))
        feat.min_value = float(np.min(values))
        feat.max_value = float(np.max(values))
        feat.updated_at = datetime.now(UTC)

        if feat.feature_type == FeatureType.CATEGORICAL:
            feat.unique_values = list(np.unique(values))[:100]  # Limit

        self._save_store()

    def create_version(self, version: str, description: str = "") -> FeatureVersion:
        """Create a versioned snapshot of current feature definitions"""
        fv = FeatureVersion(
            version=version,
            created_at=datetime.now(UTC),
            feature_definitions=self.features.copy(),
            feature_groups=self.groups.copy(),
            description=description,
        )

        self.versions[version] = fv

        # Save version snapshot
        version_path = self.storage_path / f"version_{version}.json"
        with open(version_path, "w") as f:
            json.dump(
                {
                    "version": version,
                    "description": description,
                    "created_at": fv.created_at.isoformat(),
                    "features": {name: feat.to_dict() for name, feat in fv.feature_definitions.items()},
                    "groups": {name: group.to_dict() for name, group in fv.feature_groups.items()},
                },
                f,
                indent=2,
            )

        logger.info(f"Created feature store version: {version}")
        return fv

    def load_version(self, version: str) -> bool:
        """Load a specific version of feature definitions"""
        version_path = self.storage_path / f"version_{version}.json"

        if not version_path.exists():
            logger.error(f"Version {version} not found")
            return False

        try:
            with open(version_path) as f:
                data = json.load(f)

            self.features = {
                name: FeatureDefinition.from_dict(feat_data) for name, feat_data in data.get("features", {}).items()
            }

            for name, group_data in data.get("groups", {}).items():
                group_data["created_at"] = datetime.fromisoformat(group_data["created_at"])
                self.groups[name] = FeatureGroup(**group_data)

            logger.info(f"Loaded feature store version: {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to load version {version}: {e}")
            return False

    def get_lineage(self, feature_name: str) -> dict[str, Any]:
        """Get lineage (dependencies) for a feature"""
        if feature_name not in self.features:
            return {}

        feat = self.features[feature_name]

        lineage = {
            "feature": feature_name,
            "computation": feat.computation_fn,
            "parameters": feat.parameters,
            "direct_dependencies": feat.dependencies,
            "full_lineage": [],
        }

        # Recursively get all dependencies
        visited = set()
        to_visit = list(feat.dependencies)

        while to_visit:
            dep = to_visit.pop(0)
            if dep in visited:
                continue
            visited.add(dep)

            lineage["full_lineage"].append(dep)

            dep_feat = self.features.get(dep)
            if dep_feat:
                to_visit.extend(dep_feat.dependencies)

        return lineage

    def export_definitions(self, path: str) -> None:
        """Export all feature definitions to a file"""
        data = {
            "features": {name: feat.to_dict() for name, feat in self.features.items()},
            "groups": {name: group.to_dict() for name, group in self.groups.items()},
            "exported_at": datetime.now(UTC).isoformat(),
            "total_features": len(self.features),
            "total_groups": len(self.groups),
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(self.features)} features to {path}")

    def import_definitions(self, path: str, merge: bool = True) -> int:
        """Import feature definitions from a file"""
        with open(path) as f:
            data = json.load(f)

        imported = 0

        for name, feat_data in data.get("features", {}).items():
            if merge or name not in self.features:
                self.features[name] = FeatureDefinition.from_dict(feat_data)
                imported += 1

        for name, group_data in data.get("groups", {}).items():
            if merge or name not in self.groups:
                group_data["created_at"] = datetime.fromisoformat(group_data["created_at"])
                self.groups[name] = FeatureGroup(**group_data)

        self._save_store()

        logger.info(f"Imported {imported} features from {path}")
        return imported
