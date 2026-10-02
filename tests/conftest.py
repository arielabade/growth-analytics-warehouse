"""Shared fixtures: a tiny end-to-end SYNTHETIC warehouse built once per test session."""
import pytest

from src.generate.config import load_config
from src.generate.messify import write_raw
from src.pipeline.run import run_pipeline


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("gaw")
    cfg = load_config(profile="small")
    write_raw(d / "raw", cfg)
    db = d / "gaw.duckdb"
    res = run_pipeline(db_path=db, raw_dir=d / "raw", cfg=cfg)
    return {"db": db, "raw": d / "raw", "res": res, "cfg": cfg}


@pytest.fixture()
def con(built):
    import duckdb

    c = duckdb.connect(str(built["db"]), read_only=True)
    yield c
    c.close()
