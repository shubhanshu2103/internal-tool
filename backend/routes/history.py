"""
routes/history.py

GET  /history             — list all past evaluations, newest first
PATCH /history/{review_id} — update disposition (APPROVED / DECLINED / PENDING)
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from models import HistoryEntry, DispositionUpdate, Disposition
from config import settings
from datetime import datetime, timezone

router = APIRouter(prefix="/history", tags=["history"])


def _outputs_dir() -> Path:
    p = Path(settings.outputs_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_entry(path: Path) -> HistoryEntry:
    data = json.loads(path.read_text())
    return HistoryEntry(**data["history"])


@router.get("")
def list_history():
    entries = []
    for f in sorted(_outputs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            entries.append(_load_entry(f).model_dump())
        except Exception:
            continue
    return {"total": len(entries), "entries": entries}


@router.patch("/{review_id}")
def update_disposition(review_id: str, body: DispositionUpdate):
    path = _outputs_dir() / f"{review_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evaluation not found.")

    data = json.loads(path.read_text())
    data["history"]["disposition"] = body.disposition.value
    data["history"]["disposed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2))

    return {"status": "updated", "review_id": review_id, "disposition": body.disposition.value}
