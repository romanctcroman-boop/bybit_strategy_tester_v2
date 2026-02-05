"""
CGAN (Conditional GAN) for Limit Order Book generation.

Condition: mid_price (log), spread_bps, volatility
Output: synthetic LOB (top N bid/ask levels)

Requires: pip install torch
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Optional PyTorch
try:
    import torch
    import torch.nn as nn

    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False
    torch = None
    nn = None

# Default LOB representation: top 20 bids + 20 asks
# Each level: (price_rel, size) — price relative to mid in bps
NUM_LEVELS = 20
COND_DIM = 4  # log_mid, spread_bps, volatility, time_of_day
NOISE_DIM = 32
LOB_DIM = NUM_LEVELS * 4  # bid_price_rel, bid_size, ask_price_rel, ask_size


def _to_tensor(x: np.ndarray, device: str = "cpu") -> torch.Tensor:
    if not _HAS_TORCH:
        raise ImportError("PyTorch required: pip install torch")
    return torch.from_numpy(x).float().to(device)


if _HAS_TORCH:

    class Generator(nn.Module):
        """Generator: (noise, condition) -> synthetic LOB vector."""

        def __init__(
            self,
            noise_dim: int = NOISE_DIM,
            cond_dim: int = COND_DIM,
            hidden: int = 128,
            out_dim: int = LOB_DIM,
        ):
            super().__init__()
            self.noise_dim = noise_dim
            self.cond_dim = cond_dim
            self.fc = nn.Sequential(
                nn.Linear(noise_dim + cond_dim, hidden),
                nn.LeakyReLU(0.2),
                nn.Linear(hidden, hidden * 2),
                nn.LeakyReLU(0.2),
                nn.Linear(hidden * 2, hidden),
                nn.LeakyReLU(0.2),
                nn.Linear(hidden, out_dim),
                nn.Tanh(),  # Output in [-1, 1], will scale later
            )

        def forward(self, z: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
            x = torch.cat([z, c], dim=1)
            return self.fc(x)

    class Discriminator(nn.Module):
        """Discriminator: (LOB, condition) -> real/fake score."""

        def __init__(
            self,
            lob_dim: int = LOB_DIM,
            cond_dim: int = COND_DIM,
            hidden: int = 128,
        ):
            super().__init__()
            self.fc = nn.Sequential(
                nn.Linear(lob_dim + cond_dim, hidden * 2),
                nn.LeakyReLU(0.2),
                nn.Dropout(0.3),
                nn.Linear(hidden * 2, hidden),
                nn.LeakyReLU(0.2),
                nn.Dropout(0.3),
                nn.Linear(hidden, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
            inp = torch.cat([x, c], dim=1)
            return self.fc(inp)

    class LOB_CGAN:
        """Conditional GAN for LOB generation."""

        def __init__(
            self,
            num_levels: int = NUM_LEVELS,
            noise_dim: int = NOISE_DIM,
            cond_dim: int = COND_DIM,
            lr: float = 0.0002,
            device: str | None = None,
        ):
            if not _HAS_TORCH:
                raise ImportError("PyTorch required: pip install torch")
            self.num_levels = num_levels
            lob_dim = num_levels * 4
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

            self.generator = Generator(
                noise_dim=noise_dim,
                cond_dim=cond_dim,
                out_dim=lob_dim,
            ).to(self.device)
            self.discriminator = Discriminator(
                lob_dim=lob_dim,
                cond_dim=cond_dim,
            ).to(self.device)

            self.optimizer_g = torch.optim.Adam(
                self.generator.parameters(), lr=lr, betas=(0.5, 0.999)
            )
            self.optimizer_d = torch.optim.Adam(
                self.discriminator.parameters(), lr=lr, betas=(0.5, 0.999)
            )
            self.criterion = nn.BCELoss()

            # Normalization stats (set during fit)
            self._mid_mean = 0.0
            self._mid_std = 1.0
            self._spread_mean = 10.0
            self._spread_std = 5.0
            self._size_scale = 100.0

        def _lob_to_vector(
            self,
            bids: list[tuple[float, float]],
            asks: list[tuple[float, float]],
            mid: float,
            spread: float,
        ) -> np.ndarray:
            """Convert (price, size) lists to normalized vector."""
            spread = max(spread, 1e-8)
            vec = np.zeros(self.num_levels * 4, dtype=np.float32)
            for i in range(min(self.num_levels, len(bids))):
                p, s = bids[i]
                vec[i] = (p - mid) / spread  # relative price in spread units
                vec[self.num_levels + i] = np.log1p(s) / np.log1p(self._size_scale)
            for i in range(min(self.num_levels, len(asks))):
                p, s = asks[i]
                vec[self.num_levels * 2 + i] = (p - mid) / spread
                vec[self.num_levels * 3 + i] = np.log1p(s) / np.log1p(self._size_scale)
            return vec

        def _vector_to_lob(
            self,
            vec: np.ndarray,
            mid: float,
            spread: float,
        ) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
            """Convert vector back to (bids, asks)."""
            spread = max(spread, 1e-8)
            bids = []
            asks = []
            for i in range(self.num_levels):
                # Clamp and scale
                p_rel = np.clip(vec[i], -5, 0)
                s = np.expm1(np.clip(vec[self.num_levels + i], -1, 1) * np.log1p(self._size_scale))
                s = max(0, float(s))
                bids.append((mid + p_rel * spread, s))
            for i in range(self.num_levels):
                p_rel = np.clip(vec[self.num_levels * 2 + i], 0, 5)
                s = np.expm1(
                    np.clip(vec[self.num_levels * 3 + i], -1, 1) * np.log1p(self._size_scale)
                )
                s = max(0, float(s))
                asks.append((mid + p_rel * spread, s))
            return bids, asks

        def fit(
            self,
            data_path: Path,
            epochs: int = 100,
            batch_size: int = 64,
        ) -> list[float]:
            """Train on NDJSON L2 data."""
            from backend.experimental.l2_lob.generative_research import load_lob_dataset

            dataset = load_lob_dataset(data_path)
            if len(dataset) < batch_size * 2:
                raise ValueError(f"Need at least {batch_size * 2} samples, got {len(dataset)}")

            # Build condition + LOB vectors
            conds = []
            lobs = []
            for d in dataset:
                mid = d["mid"]
                spread_bps = d.get("spread_bps", 1.0)
                spread = mid * (spread_bps / 10000)
                bids = [(float(b[0]), float(b[1])) for b in d.get("bids", [])[: self.num_levels]]
                asks = [(float(a[0]), float(a[1])) for a in d.get("asks", [])[: self.num_levels]]
                if not bids or not asks:
                    continue
                # Condition: log_mid (normalized), spread_bps, vol proxy, 0
                cond = np.array(
                    [
                        np.log1p(mid) / 15,
                        spread_bps / 50,
                        0.5,
                        0.0,
                    ],
                    dtype=np.float32,
                )[:COND_DIM]
                if len(cond) < COND_DIM:
                    cond = np.pad(cond, (0, COND_DIM - len(cond)))
                vec = self._lob_to_vector(bids, asks, mid, spread)
                conds.append(cond)
                lobs.append(vec)

            conds = np.array(conds, dtype=np.float32)
            lobs = np.array(lobs, dtype=np.float32)
            # Normalize lobs to [-1, 1] for tanh output
            lob_min, lob_max = lobs.min(axis=0), lobs.max(axis=0)
            lob_range = np.where(lob_max - lob_min > 1e-8, lob_max - lob_min, 1.0)
            lobs_norm = 2 * (lobs - lob_min) / lob_range - 1
            self._lob_min = lob_min
            self._lob_max = lob_max
            self._lob_range = lob_range

            losses_g = []
            n = len(lobs_norm)
            for ep in range(epochs):
                perm = np.random.permutation(n)
                epoch_loss_g = 0.0
                n_batches = 0
                for start in range(0, n, batch_size):
                    end = min(start + batch_size, n)
                    idx = perm[start:end]
                    batch_lob = lobs_norm[idx]
                    batch_cond = conds[idx]
                    bs = len(idx)

                    # Train discriminator
                    self.optimizer_d.zero_grad()
                    z = torch.randn(bs, NOISE_DIM, device=self.device)
                    fake_lob = self.generator(z, _to_tensor(batch_cond, self.device))
                    real_out = self.discriminator(
                        _to_tensor(batch_lob, self.device),
                        _to_tensor(batch_cond, self.device),
                    )
                    fake_out = self.discriminator(fake_lob.detach(), _to_tensor(batch_cond, self.device))
                    loss_d = self.criterion(real_out, torch.ones(bs, 1, device=self.device)) + self.criterion(
                        fake_out, torch.zeros(bs, 1, device=self.device)
                    )
                    loss_d.backward()
                    self.optimizer_d.step()

                    # Train generator
                    self.optimizer_g.zero_grad()
                    fake_out = self.discriminator(fake_lob, _to_tensor(batch_cond, self.device))
                    loss_g = self.criterion(fake_out, torch.ones(bs, 1, device=self.device))
                    loss_g.backward()
                    self.optimizer_g.step()

                    epoch_loss_g += loss_g.item()
                    n_batches += 1

                avg_loss = epoch_loss_g / max(n_batches, 1)
                losses_g.append(avg_loss)
                if (ep + 1) % 10 == 0:
                    logger.info("Epoch %d G_loss=%.4f", ep + 1, avg_loss)

            return losses_g

        def generate(
            self,
            mid_price: float,
            spread_bps: float = 10.0,
            n_samples: int = 1,
        ) -> list[tuple[list[tuple[float, float]], list[tuple[float, float]]]]:
            """Generate synthetic LOB(s)."""
            spread = mid_price * (spread_bps / 10000)
            cond = np.array(
                [np.log1p(mid_price) / 15, spread_bps / 50, 0.5, 0.0],
                dtype=np.float32,
            )[:COND_DIM]
            if len(cond) < COND_DIM:
                cond = np.pad(cond, (0, COND_DIM - len(cond)))
            cond_batch = np.tile(cond, (n_samples, 1)).astype(np.float32)

            self.generator.eval()
            with torch.no_grad():
                z = torch.randn(n_samples, NOISE_DIM, device=self.device)
                c = _to_tensor(cond_batch, self.device)
                out = self.generator(z, c)
                vec = out.cpu().numpy()
                # Denormalize
                if hasattr(self, "_lob_min"):
                    vec = (vec + 1) / 2 * self._lob_range + self._lob_min

            result = []
            for i in range(n_samples):
                bids, asks = self._vector_to_lob(vec[i], mid_price, spread)
                result.append((bids, asks))
            return result

        def save(self, path: Path) -> None:
            """Save model state."""
            state = {
                "generator": self.generator.state_dict(),
                "discriminator": self.discriminator.state_dict(),
                "num_levels": self.num_levels,
                "_lob_min": getattr(self, "_lob_min", None),
                "_lob_max": getattr(self, "_lob_max", None),
                "_lob_range": getattr(self, "_lob_range", None),
            }
            torch.save(state, path)

        @classmethod
        def load(cls, path: Path, device: str | None = None) -> LOB_CGAN:
            """Load model from file."""
            dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
            state = torch.load(path, map_location=dev)
            model = cls(num_levels=state.get("num_levels", NUM_LEVELS), device=dev)
            model.generator.load_state_dict(state["generator"])
            model.discriminator.load_state_dict(state["discriminator"])
            if state.get("_lob_min") is not None:
                model._lob_min = state["_lob_min"]
                model._lob_max = state["_lob_max"]
                model._lob_range = state["_lob_range"]
            return model

else:
    LOB_CGAN = None  # type: ignore
    Generator = None  # type: ignore
    Discriminator = None  # type: ignore
