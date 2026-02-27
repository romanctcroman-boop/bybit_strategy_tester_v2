"""Tests for P3-7: Blockchain-Verified Backtests."""

import pytest

from backend.research import BacktestProof, BacktestVerifier


@pytest.fixture
def verifier():
    return BacktestVerifier()


@pytest.fixture
def sample_config():
    return {"strategy": "RSI", "period": 14, "symbol": "BTCUSDT"}


@pytest.fixture
def sample_results():
    return {"total_return": 0.25, "sharpe": 1.5, "max_drawdown": -0.1}


@pytest.fixture
def proof(verifier, sample_config, sample_results):
    return verifier.create_proof(
        backtest_id="bt_test_001",
        strategy_config=sample_config,
        data_config={"symbol": "BTCUSDT", "timeframe": "15"},
        results=sample_results,
    )


class TestBacktestProof:
    def test_fields_present(self, proof):
        assert proof.backtest_id == "bt_test_001"
        assert isinstance(proof.timestamp, str)
        assert len(proof.strategy_hash) == 64  # SHA-256 hex
        assert len(proof.data_hash) == 64
        assert len(proof.results_hash) == 64
        assert len(proof.signature) == 64

    def test_to_dict(self, proof):
        d = proof.to_dict()
        assert d["backtest_id"] == "bt_test_001"
        assert "signature" in d
        assert "verified" in d

    def test_from_dict_roundtrip(self, proof):
        d = proof.to_dict()
        restored = BacktestProof.from_dict(d)
        assert restored.backtest_id == proof.backtest_id
        assert restored.signature == proof.signature


class TestBacktestVerifier:
    def test_init(self, verifier):
        assert len(verifier.proofs) == 0
        assert len(verifier.chain) == 0

    def test_hash_data_dict(self, verifier):
        h = verifier.hash_data({"a": 1, "b": 2})
        assert len(h) == 64
        assert isinstance(h, str)

    def test_hash_data_deterministic(self, verifier):
        data = {"strategy": "RSI", "period": 14}
        h1 = verifier.hash_data(data)
        h2 = verifier.hash_data(data)
        assert h1 == h2

    def test_hash_data_different_data_different_hash(self, verifier):
        h1 = verifier.hash_data({"a": 1})
        h2 = verifier.hash_data({"a": 2})
        assert h1 != h2

    def test_hash_data_string(self, verifier):
        h = verifier.hash_data("hello world")
        assert len(h) == 64

    def test_create_proof_returns_backtest_proof(self, proof):
        assert isinstance(proof, BacktestProof)

    def test_create_proof_stored_in_chain(self, verifier, proof):
        assert len(verifier.chain) == 1
        assert len(verifier.proofs) == 1

    def test_create_proof_verified_true(self, proof):
        assert proof.verified is True

    def test_verify_proof_valid(self, verifier, proof):
        is_valid = verifier.verify_proof(proof)
        assert is_valid is True

    def test_verify_proof_tampered_fails(self, verifier, proof):
        # Tamper with the signature
        tampered = BacktestProof(
            backtest_id=proof.backtest_id,
            timestamp=proof.timestamp,
            strategy_hash=proof.strategy_hash,
            data_hash=proof.data_hash,
            results_hash=proof.results_hash,
            signature="0" * 64,  # wrong signature
        )
        assert verifier.verify_proof(tampered) is False

    def test_verify_chain_all_valid(self, verifier, sample_config, sample_results):
        verifier.create_proof("bt_1", sample_config, {}, sample_results)
        verifier.create_proof("bt_2", sample_config, {}, sample_results)
        assert verifier.verify_chain() is True

    def test_get_proof_returns_correct(self, verifier, proof):
        retrieved = verifier.get_proof("bt_test_001")
        assert retrieved is proof

    def test_get_proof_missing_returns_none(self, verifier):
        assert verifier.get_proof("nonexistent") is None

    def test_export_proof(self, verifier, proof):
        exported = verifier.export_proof("bt_test_001")
        assert isinstance(exported, dict)
        assert exported["backtest_id"] == "bt_test_001"

    def test_export_proof_missing_returns_none(self, verifier):
        assert verifier.export_proof("nonexistent") is None

    def test_import_proof(self, verifier, proof):
        exported = verifier.export_proof("bt_test_001")
        v2 = BacktestVerifier()
        imported = v2.import_proof(exported)
        assert imported.backtest_id == "bt_test_001"
        assert imported.signature == proof.signature

    def test_get_chain_summary(self, verifier, sample_config, sample_results):
        verifier.create_proof("c1", sample_config, {}, sample_results)
        verifier.create_proof("c2", sample_config, {}, sample_results)
        summary = verifier.get_chain_summary()
        assert summary["total_proofs"] == 2
        assert summary["first_backtest"] == "c1"
        assert summary["last_backtest"] == "c2"

    def test_get_chain_summary_empty(self, verifier):
        summary = verifier.get_chain_summary()
        assert summary["total_proofs"] == 0
        assert summary["first_backtest"] is None
