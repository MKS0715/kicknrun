from __future__ import annotations

from copy import deepcopy
from threading import RLock
from time import time
from typing import Any

MIN_PLAYERS = 1
MAX_PLAYERS = 12
DEFAULT_COUNTS = {"A": 8, "B": 9}
CONTROLLER_LEASE_SECONDS = 15.0


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


def initial_positions(team: str, count: int, offense_team: str) -> list[dict[str, Any]]:
    """Create percentage-based positions for the kick-and-run tactics board."""
    count = max(MIN_PLAYERS, min(MAX_PLAYERS, int(count)))
    offense = team == offense_team

    if offense:
        result: list[dict[str, Any]] = []
        for idx in range(count):
            if idx == 0:
                result.append({"id": 1, "x": 50.0, "y": 84.0, "status": "field"})
            else:
                result.append({"id": idx + 1, "x": 50.0, "y": 84.0, "status": "bench"})
        return result

    rows = [
        (34.0, [18, 34, 50, 66, 82]),
        (46.0, [25, 42, 58, 75]),
        (56.0, [35, 50, 65]),
    ]
    coords: list[tuple[float, float]] = []
    for y, xs in rows:
        coords.extend((float(x), y) for x in xs)

    return [
        {"id": idx + 1, "x": coords[idx][0], "y": coords[idx][1], "status": "field"}
        for idx in range(count)
    ]


def make_initial_board(strategy_team: str, counts: dict[str, int] | None = None) -> dict[str, Any]:
    counts = deepcopy(counts or DEFAULT_COUNTS)
    offense = strategy_team if strategy_team in ("A", "B") else "A"
    return {
        "counts": counts,
        "offense": offense,
        "current_kicker": 1,
        "players": {
            "A": initial_positions("A", counts["A"], offense),
            "B": initial_positions("B", counts["B"], offense),
        },
        "ball": {"x": 50.0, "y": 78.0},
        "revision": 0,
        "last_change_id": "",
        "updated_at": time(),
    }


def _normalize_players(
    players: Any,
    team: str,
    count: int,
    offense_team: str,
) -> list[dict[str, Any]]:
    defaults = initial_positions(team, count, offense_team)
    by_id: dict[int, dict[str, Any]] = {}

    if isinstance(players, list):
        for raw in players:
            if not isinstance(raw, dict):
                continue
            pid = _safe_int(raw.get("id"), -1)
            if not 1 <= pid <= count:
                continue
            default = defaults[pid - 1]
            status = raw.get("status", default["status"])
            if status not in ("field", "bench"):
                status = default["status"]
            if team != offense_team:
                status = "field"
            by_id[pid] = {
                "id": pid,
                "x": _clamp(_safe_float(raw.get("x"), float(default["x"])), 2.0, 98.0),
                "y": _clamp(_safe_float(raw.get("y"), float(default["y"])), 2.0, 98.0),
                "status": status,
            }

    return [deepcopy(by_id.get(pid, defaults[pid - 1])) for pid in range(1, count + 1)]


def _ensure_current_kicker(players: list[dict[str, Any]], current_kicker: int) -> None:
    for player in players:
        if int(player["id"]) == current_kicker:
            if player.get("status") != "field":
                player["status"] = "field"
                player["x"] = 50.0
                player["y"] = 84.0
            return


class SharedGameStore:
    """Thread-safe in-memory state shared across Streamlit browser sessions.

    Each team has one shared private tactics board and one temporary controller
    lease. Only the device holding the lease is allowed to write to that board.
    Other devices always render the same server snapshot in view-only mode.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._counts = deepcopy(DEFAULT_COUNTS)
        self._boards = {
            "A": make_initial_board("A", self._counts),
            "B": make_initial_board("B", self._counts),
        }
        self._controllers: dict[str, dict[str, Any] | None] = {"A": None, "B": None}

    @staticmethod
    def _team(strategy_team: str) -> str:
        return strategy_team if strategy_team in ("A", "B") else "A"

    def _expire_controller_locked(self, team: str) -> None:
        controller = self._controllers.get(team)
        if controller is None:
            return
        if time() - float(controller.get("last_seen", 0.0)) > CONTROLLER_LEASE_SECONDS:
            self._controllers[team] = None

    def controller_status(self, strategy_team: str) -> dict[str, Any]:
        team = self._team(strategy_team)
        with self._lock:
            self._expire_controller_locked(team)
            controller = self._controllers.get(team)
            if controller is None:
                return {"active": False, "client_id": None, "expires_in": 0.0}
            expires_in = max(
                0.0,
                CONTROLLER_LEASE_SECONDS - (time() - float(controller["last_seen"])),
            )
            return {
                "active": True,
                "client_id": str(controller["client_id"]),
                "expires_in": expires_in,
            }

    def claim_controller(self, strategy_team: str, client_id: str) -> bool:
        team = self._team(strategy_team)
        client_id = str(client_id)
        with self._lock:
            self._expire_controller_locked(team)
            controller = self._controllers.get(team)
            if controller is not None and str(controller["client_id"]) != client_id:
                return False
            self._controllers[team] = {"client_id": client_id, "last_seen": time()}
            return True

    def touch_controller(self, strategy_team: str, client_id: str) -> bool:
        team = self._team(strategy_team)
        client_id = str(client_id)
        with self._lock:
            self._expire_controller_locked(team)
            controller = self._controllers.get(team)
            if controller is None or str(controller["client_id"]) != client_id:
                return False
            controller["last_seen"] = time()
            return True

    def is_controller(self, strategy_team: str, client_id: str) -> bool:
        team = self._team(strategy_team)
        client_id = str(client_id)
        with self._lock:
            self._expire_controller_locked(team)
            controller = self._controllers.get(team)
            return controller is not None and str(controller["client_id"]) == client_id

    def release_controller(self, strategy_team: str, client_id: str | None = None, *, force: bool = False) -> bool:
        team = self._team(strategy_team)
        with self._lock:
            self._expire_controller_locked(team)
            controller = self._controllers.get(team)
            if controller is None:
                return True
            if force or (client_id is not None and str(controller["client_id"]) == str(client_id)):
                self._controllers[team] = None
                return True
            return False

    def snapshot(self, strategy_team: str) -> dict[str, Any]:
        team = self._team(strategy_team)
        with self._lock:
            board = deepcopy(self._boards[team])
            board["counts"] = deepcopy(self._counts)
            return board

    def update_board(
        self,
        strategy_team: str,
        incoming: Any,
        *,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        team = self._team(strategy_team)
        if not isinstance(incoming, dict):
            return self.snapshot(team)

        with self._lock:
            if client_id is not None:
                self._expire_controller_locked(team)
                controller = self._controllers.get(team)
                if controller is None or str(controller["client_id"]) != str(client_id):
                    return deepcopy(self._boards[team])
                controller["last_seen"] = time()

            incoming_counts = incoming.get("counts", {})
            if isinstance(incoming_counts, dict):
                for label in ("A", "B"):
                    current = self._counts[label]
                    raw = _safe_int(incoming_counts.get(label), current)
                    self._counts[label] = max(MIN_PLAYERS, min(MAX_PLAYERS, raw))

            current = self._boards[team]
            offense = incoming.get("offense")
            if offense not in ("A", "B"):
                offense = current["offense"]

            current_kicker = _safe_int(
                incoming.get("current_kicker"),
                int(current.get("current_kicker", 1)),
            )
            current_kicker = max(1, min(self._counts[offense], current_kicker))

            incoming_players = incoming.get("players", {})
            if not isinstance(incoming_players, dict):
                incoming_players = {}

            normalized_players = {
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
            _ensure_current_kicker(normalized_players[offense], current_kicker)

            current["offense"] = offense
            current["current_kicker"] = current_kicker
            current["counts"] = deepcopy(self._counts)
            current["players"] = normalized_players

            ball = incoming.get("ball", {})
            if not isinstance(ball, dict):
                ball = {}
            current_ball = current.get("ball", {"x": 50.0, "y": 78.0})
            current["ball"] = {
                "x": _clamp(_safe_float(ball.get("x"), current_ball["x"]), 2.0, 98.0),
                "y": _clamp(_safe_float(ball.get("y"), current_ball["y"]), 2.0, 98.0),
            }

            change_id = str(incoming.get("client_change_id") or "")[:120]
            current["last_change_id"] = change_id
            current["revision"] = int(current.get("revision", 0)) + 1
            current["updated_at"] = time()

            # Counts are common to both rooms. Resize the other room while
            # preserving its own strategy and player locations.
            other_team = "B" if team == "A" else "A"
            other = self._boards[other_team]
            other_offense = other.get("offense", other_team)
            other_kicker = max(
                1,
                min(
                    self._counts[other_offense],
                    _safe_int(other.get("current_kicker"), 1),
                ),
            )
            other_players = {
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
            _ensure_current_kicker(other_players[other_offense], other_kicker)
            other["counts"] = deepcopy(self._counts)
            other["current_kicker"] = other_kicker
            other["players"] = other_players
            other["revision"] = int(other.get("revision", 0)) + 1
            other["updated_at"] = time()

            return deepcopy(current)

    def reset_board(self, strategy_team: str) -> dict[str, Any]:
        team = self._team(strategy_team)
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
