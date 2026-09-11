import unittest

from game_state import MAX_PLAYERS, SharedGameStore


class SharedGameStoreTests(unittest.TestCase):
    def test_default_counts(self):
        store = SharedGameStore()
        state = store.snapshot("A")
        self.assertEqual(state["counts"], {"A": 8, "B": 9})
        self.assertEqual(len(state["players"]["A"]), 8)
        self.assertEqual(len(state["players"]["B"]), 9)

    def test_count_change_resizes_both_private_boards(self):
        store = SharedGameStore()
        state_a = store.snapshot("A")
        state_a["counts"] = {"A": 10, "B": 7}
        store.update_board("A", state_a)
        self.assertEqual(len(store.snapshot("A")["players"]["A"]), 10)
        self.assertEqual(len(store.snapshot("B")["players"]["A"]), 10)
        self.assertEqual(len(store.snapshot("B")["players"]["B"]), 7)

    def test_positions_are_clamped(self):
        store = SharedGameStore()
        state = store.snapshot("A")
        state["players"]["A"][0]["x"] = 999
        state["players"]["A"][0]["y"] = -100
        state["ball"] = {"x": -1, "y": 200}
        updated = store.update_board("A", state)
        self.assertEqual(updated["players"]["A"][0]["x"], 98.0)
        self.assertEqual(updated["players"]["A"][0]["y"], 2.0)
        self.assertEqual(updated["ball"], {"x": 2.0, "y": 98.0})

    def test_counts_are_bounded(self):
        store = SharedGameStore()
        state = store.snapshot("B")
        state["counts"] = {"A": 999, "B": 0}
        updated = store.update_board("B", state)
        self.assertEqual(updated["counts"]["A"], MAX_PLAYERS)
        self.assertEqual(updated["counts"]["B"], 1)


if __name__ == "__main__":
    unittest.main()
