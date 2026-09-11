from __future__ import annotations

from copy import deepcopy
from threading import RLock
from time import time
from typing import Any

MIN_PLAYERS = 1
MAX_PLAYERS = 12
DEFAULT_COUNTS = {"A": 8, "B": 9}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def initial_positions(team: str, count: int, offense_team: str) -> list[dict[str, float | int]]:
    """Create simple percentage-based positions for a kick-and-run tactics board."""
    count = max(MIN_PLAYERS, min(MAX_PLAYERS, int(count)))
    offense = team == offense_team

    if offense:
        rows = [
            (84.0, [18, 34, 50, 66, 82]),
            (74.0, [25, 42, 58, 75]),
            (66.0, [35, 50, 65]),
        ]
    else:
        rows = [
            (35.0, [18, 34, 50, 66, 82]),
            (47.0, [25, 42, 58, 75]),
            (57.0, [35, 50, 65]),
        ]

    coords: list[tuple[float, float]] = []
    for y, xs in rows:
        coords.extend((float(x), y) for x in xs)

    # MAX_PLAYERS is 12, and rows provide 12 positions.
    result = []
    for idx in range(count):
        x, y = coords[idx]
        result.append({"id": idx + 1, "x": x, "y": y})
    return result


def make_initial_board(strategy_team: str, counts: dict[str, int] | None = None) -> dict[str, Any]:
    counts = deepcopy(counts or DEFAULT_COUNTS)
    offense = strategy_team if strategy_team in ("A", "B") else "A"
    return {
        "counts": counts,
        "offense": offense,
        "players": {
            "A": initial_positions("A", counts["A"], offense),
            "B": initial_positions("B", counts["B"], offense),
        },
        "ball": {"x": 50.0, "y": 79.0},
        "revision": 0,
        "updated_at": time(),
    }


def _normalize_players(
    players: Any,
    team: str,
    count: int,
    offense_team: str,
) -> list[dict[str, float | int]]:
    defaults = initial_positions(team, count, offense_team)
    by_id: dict[int, dict[str, float | int]] = {}

    if isinstance(players, list):
        for raw in players:
            if not isinstance(raw, dict):
                continue
            pid = _safe_int(raw.get("id"), -1)
            if not 1 <= pid <= count:
                continue
            default = defaults[pid - 1]
            by_id[pid] = {
                "id": pid,
                "x": _clamp(_safe_float(raw.get("x"), float(default["x"])), 2.0, 98.0),
                "y": _clamp(_safe_float(raw.get("y"), float(default["y"])), 2.0, 98.0),
            }

    output = []
    for pid in range(1, count + 1):
        output.append(by_id.get(pid, defaults[pid - 1]))
    return output


class SharedGameStore:
    """Thread-safe in-memory state shared across Streamlit browser sessions."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._counts = deepcopy(DEFAULT_COUNTS)
        self._boards = {
            "A": make_initial_board("A", self._counts),
            "B": make_initial_board("B", self._counts),
        }

    def snapshot(self, strategy_team: str) -> dict[str, Any]:
        team = strategy_team if strategy_team in ("A", "B") else "A"
        with self._lock:
            board = deepcopy(self._boards[team])
            board["counts"] = deepcopy(self._counts)
            return board

    def update_board(self, strategy_team: str, incoming: Any) -> dict[str, Any]:
        team = strategy_team if strategy_team in ("A", "B") else "A"
        if not isinstance(incoming, dict):
            return self.snapshot(team)

        with self._lock:
            incoming_counts = incoming.get("counts", {})
            if isinstance(incoming_counts, dict):
                for label in ("A", "B"):
                    current = self._counts[label]
                    raw = _safe_int(incoming_counts.get(label), current)
                    self._counts[label] = max(MIN_PLAYERS, min(MAX_PLAYERS, raw))

            offense = incoming.get("offense")
            if offense not in ("A", "B"):
                offense = self._boards[team]["offense"]

            incoming_players = incoming.get("players", {})
            if not isinstance(incoming_players, dict):
                incoming_players = {}

            current = self._boards[team]
            current["offense"] = offense
            current["counts"] = deepcopy(self._counts)
            current["players"] = {
                "A": _normalize_players(
                    incoming_players.get("A", current["players"]["A"]),
                    "A",
                    self._counts["A"],
                    offense,
                ),
                "B": _normalize_players(
                    incoming_players.get("B", current["players"]["B"]),
                    "B",
                    self._counts["B"],
                    offense,
                ),
            }

            ball = incoming.get("ball", {})
            if not isinstance(ball, dict):
                ball = {}
            current_ball = current.get("ball", {"x": 50.0, "y": 79.0})
            current["ball"] = {
                "x": _clamp(_safe_float(ball.get("x"), current_ball["x"]), 2.0, 98.0),
                "y": _clamp(_safe_float(ball.get("y"), current_ball["y"]), 2.0, 98.0),
            }
            current["revision"] = int(current.get("revision", 0)) + 1
            current["updated_at"] = time()

            # Player counts are shared globally. Resize the other private tactics board,
            # but preserve its own positions and strategy choices.
            other_team = "B" if team == "A" else "A"
            other = self._boards[other_team]
            other_offense = other.get("offense", other_team)
            other["counts"] = deepcopy(self._counts)
            other["players"] = {
                "A": _normalize_players(
                    other.get("players", {}).get("A", []),
                    "A",
                    self._counts["A"],
                    other_offense,
                ),
                "B": _normalize_players(
                    other.get("players", {}).get("B", []),
                    "B",
                    self._counts["B"],
                    other_offense,
                ),
            }
            other["revision"] = int(other.get("revision", 0)) + 1
            other["updated_at"] = time()

            return deepcopy(current)

    def reset_board(self, strategy_team: str) -> dict[str, Any]:
        team = strategy_team if strategy_team in ("A", "B") else "A"
        with self._lock:
            self._boards[team] = make_initial_board(team, self._counts)
            return deepcopy(self._boards[team])

    def reset_all(self) -> None:
        with self._lock:
            self._counts = deepcopy(DEFAULT_COUNTS)
            self._boards = {
                "A": make_initial_board("A", self._counts),
                "B": make_initial_board("B", self._counts),
            }
