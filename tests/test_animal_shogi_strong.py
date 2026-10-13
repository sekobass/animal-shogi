import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from animal_shogi_strong import Game, Piece, Position, search


def position(turn=0):
    p = Position(turn=turn)
    p.board[3][1] = Piece('lion', 0)
    p.board[0][1] = Piece('lion', 1)
    return p


class RulesTests(unittest.TestCase):
    def test_lion_capture_finishes_immediately(self):
        p = position()
        p.board[1][1] = Piece('giraffe', 0)
        p.play(('move', 1, 1, 0, 1))
        self.assertTrue(p.finished)
        self.assertEqual(p.winner, 0)
        self.assertEqual(p.hands[0], [])
        self.assertEqual(p.legal_moves(), [])
        with self.assertRaises(ValueError):
            p.play(('move', 3, 1, 2, 1))

    def test_search_stops_before_generating_post_capture_moves(self):
        p = position(turn=1)
        p.board[3][1] = None
        with patch.object(p, 'legal_moves', side_effect=AssertionError('continued search')):
            score, move = search(p, 4)
        self.assertGreater(score, 1000)
        self.assertIsNone(move)

    def test_ai_selects_immediate_capture(self):
        p = position(turn=1)
        p.board[2][1] = Piece('giraffe', 1)
        score, move = search(p)
        self.assertEqual(move, ('move', 2, 1, 3, 1))
        self.assertGreater(score, 1000)

    def test_promotion_capture_and_unpromoted_drop(self):
        p = position()
        p.board[1][0] = Piece('chick', 0)
        p.board[0][2] = Piece('giraffe', 1)
        p.play(('move', 1, 0, 0, 0))
        self.assertTrue(p.board[0][0].promoted)
        # Capture the hen with the opponent lion.
        p.play(('move', 0, 1, 0, 0))
        self.assertEqual(p.hands[1][0].name, 'chick')
        self.assertFalse(p.hands[1][0].promoted)
        p.play(('move', 3, 1, 2, 1))
        p.play(('drop', 0, 1, 2))
        self.assertEqual(p.board[1][2].owner, 1)
        self.assertFalse(p.board[1][2].promoted)
        self.assertFalse(p.hands[1])

    def test_drop_requires_empty_square_and_existing_hand(self):
        p = position()
        p.hands[0].append(Piece('giraffe', 0))
        self.assertIn(('drop', 0, 2, 0), p.legal_moves())
        for move in [('drop', 0, 3, 1), ('drop', 1, 2, 0), ('move', 2, 0, 1, 0)]:
            with self.assertRaises(ValueError):
                p.play(move)
        p.play(('drop', 0, 2, 0))
        self.assertEqual(p.board[2][0].name, 'giraffe')

    def test_search_moves_only_existing_owned_pieces_and_preserves_root(self):
        p = position(turn=1)
        before = [[None if v is None else (v.name, v.owner) for v in row] for row in p.board]
        _, move = search(p)
        self.assertIn(move, p.legal_moves())
        self.assertEqual(p.board[move[1]][move[2]].owner, 1)
        self.assertEqual(before, [[None if v is None else (v.name, v.owner) for v in row] for row in p.board])

    def test_gui_and_search_use_same_moves(self):
        g = Game.__new__(Game)
        g.position = position()
        for r, row in enumerate(g.board):
            for c, piece in enumerate(row):
                if piece:
                    expected = [(mv[3], mv[4]) for mv in g.position.legal_moves()
                                if mv[0] == 'move' and mv[1:3] == (r, c)]
                    self.assertEqual(g.legal_moves(r, c, piece), expected)
        self.assertEqual(g.legal_moves(2, 0, Piece('lion', 0)), [])

    def test_ai_callback_does_not_move_after_game_over(self):
        g = Game.__new__(Game)
        g.position = position(turn=1)
        g.position.board[3][1] = None
        g.make_move = Mock()
        with patch('animal_shogi_strong.search') as spy:
            g.ai_move()
        spy.assert_not_called()
        g.make_move.assert_not_called()

    def test_gui_capture_cancels_ai_and_finishes_once(self):
        g = Game.__new__(Game)
        g.position = position()
        g.position.board[1][1] = Piece('giraffe', 0)
        g.ai_callback = 'pending'
        g.selected = (1, 1)
        g.window = Mock()
        g.draw = Mock()
        with patch('animal_shogi_strong.messagebox.showinfo') as info:
            g.on_click(SimpleNamespace(x=120, y=40))
            g.ai_move()
        info.assert_called_once()
        g.window.after_cancel.assert_called_once_with('pending')
        g.window.destroy.assert_called_once()
        g.window.after.assert_not_called()


if __name__ == '__main__':
    unittest.main()
