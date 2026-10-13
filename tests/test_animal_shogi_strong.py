import os
import time
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


    def test_try_success_for_both_players_stops_search(self):
        for owner in (0, 1):
            with self.subTest(owner=owner):
                p = Position(turn=owner)
                source, goal, other = (1, 0, 2) if owner == 0 else (2, 3, 1)
                p.board[source][0] = Piece('lion', owner)
                p.board[other][2] = Piece('lion', 1 - owner)
                p.play(('move', source, 0, goal, 0))
                self.assertEqual((p.winner, p.reason), (owner, 'try'))
                self.assertEqual(p.legal_moves(), [])
                self.assertIsNone(search(p)[1])

    def test_try_fails_when_enemy_can_capture(self):
        for owner in (0, 1):
            source, goal = (1, 0) if owner == 0 else (2, 3)
            attackers = [('giraffe', goal, 1, False),
                         ('elephant', source, 1, False),
                         ('lion', goal, 1, False),
                         ('chick', goal, 1, True)]
            for name, r, c, promoted in attackers:
                with self.subTest(owner=owner, attacker=name, promoted=promoted):
                    p = Position(turn=owner)
                    p.board[source][0] = Piece('lion', owner)
                    p.board[1 if owner == 0 else 2][2] = Piece('lion', 1 - owner)
                    if name == 'lion':
                        p.board[1 if owner == 0 else 2][2] = None
                    p.board[r][c] = Piece(name, 1 - owner, promoted)
                    p.play(('move', source, 0, goal, 0))
                    self.assertFalse(p.finished)
                    p.play(('move', r, c, goal, 0))
                    self.assertEqual((p.winner, p.reason), (1 - owner, 'capture'))

    def test_try_checks_enemy_chick_direction(self):
        for owner in (0, 1):
            source, goal = (1, 0) if owner == 0 else (2, 3)
            p = Position(turn=owner)
            p.board[source][1] = Piece('lion', owner)
            p.board[source][0] = Piece('chick', 1 - owner)
            p.board[1 if owner == 0 else 2][2] = Piece('lion', 1 - owner)
            p.play(('move', source, 1, goal, 0))
            self.assertEqual(p.reason, 'try')

    def test_try_ignores_own_piece_attacks_and_enemy_hand(self):
        p = Position()
        p.board[1][0] = Piece('lion', 0)
        p.board[2][2] = Piece('lion', 1)
        p.board[0][1] = Piece('giraffe', 0)
        p.hands[1] = [Piece('giraffe', 1)]
        p.play(('move', 1, 0, 0, 0))
        self.assertEqual(p.reason, 'try')

    def test_check_ignoring_and_exposed_lion_moves_are_allowed(self):
        p = position()
        p.board[2][1] = Piece('giraffe', 1)
        p.board[2][0] = Piece('giraffe', 0)
        self.assertIn(('move', 2, 0, 1, 0), p.legal_moves())
        self.assertIn(('move', 3, 1, 2, 2), p.legal_moves())
        p.play(('move', 2, 0, 1, 0))
        self.assertFalse(p.finished)
        p.play(('move', 2, 1, 3, 1))
        self.assertEqual(p.winner, 1)

    def test_unrestricted_chick_drops_and_no_pass(self):
        p = position()
        p.board[2][0] = Piece('chick', 0)
        p.hands[0] = [Piece('chick', 0), Piece('chick', 0)]
        self.assertIn(('drop', 0, 1, 0), p.legal_moves())  # two chicks in a file
        p.play(('drop', 0, 0, 0))  # immobile chick is allowed, not promoted
        self.assertFalse(p.board[0][0].promoted)
        with self.assertRaises(ValueError):
            p.play(('pass',))
        p = position()
        p.board[1][0] = Piece('giraffe', 0)
        p.board[1][2] = Piece('giraffe', 0)
        p.hands[0] = [Piece('chick', 0)]
        p.play(('drop', 0, 1, 1))  # checking/mating chick drop allowed
        self.assertTrue(p.attacked(0, 1, 0))
        self.assertFalse(p.finished)

    def test_threefold_counts_initial_position(self):
        p = position()
        cycle = [('move', 3, 1, 3, 0), ('move', 0, 1, 0, 2),
                 ('move', 3, 0, 3, 1), ('move', 0, 2, 0, 1)]
        initial = p.key()
        for move in cycle:
            p.play(move)
        self.assertFalse(p.finished)
        self.assertEqual(p.occurrences[initial], 2)
        for move in cycle:
            p.play(move)
        self.assertEqual(p.occurrences[initial], 3)
        self.assertEqual(p.reason, 'repetition')
        self.assertIsNone(p.winner)
        self.assertEqual(search(p), (0, None))
        self.assertEqual(p.legal_moves(), [])

    def test_repetition_key_includes_hands_turn_and_promotion(self):
        p = position()
        p.hands[0] = [Piece('chick', 0), Piece('giraffe', 0)]
        original = p.key()
        p.hands[0].reverse()
        self.assertEqual(original, p.key())
        for change in ('turn', 'hand_count', 'hand_owner', 'promotion'):
            q = p.clone()
            if change == 'turn':
                q.turn = 1
            elif change == 'hand_count':
                q.hands[0].append(Piece('chick', 0))
            elif change == 'hand_owner':
                q.hands[1].append(q.hands[0].pop())
            else:
                q.board[2][0] = Piece('chick', 0)
                before = q.key()
                q.board[2][0].promoted = True
                self.assertNotEqual(before, q.key())
            self.assertNotEqual(original, q.key())

    def test_search_inherits_history_and_does_not_mutate_it(self):
        p = position(turn=1)
        p.start_history()
        draw_move = ('move', 0, 1, 0, 0)
        child = p.clone()
        child.play(draw_move)
        p.occurrences[child.key()] = 2
        before = p.occurrences.copy()
        child = p.clone()
        child.play(draw_move)
        self.assertEqual(child.reason, 'repetition')
        self.assertEqual(search(child), (0, None))
        search(p.clone())
        self.assertEqual(p.occurrences, before)

    def test_ai_does_not_search_or_schedule_after_try_or_draw(self):
        for reason, winner in [('try', 0), ('try', 1), ('repetition', None)]:
            g = Game.__new__(Game)
            g.position = position(turn=1)
            g.position.reason, g.position.winner = reason, winner
            g.window = Mock()
            g.make_move = Mock()
            with patch('animal_shogi_strong.search') as spy:
                g.ai_move()
                g.end_turn()
            spy.assert_not_called()
            g.make_move.assert_not_called()
            g.window.after.assert_not_called()

    def test_search_budget_returns_legal_move_and_keeps_history(self):
        g = Game.__new__(Game)
        g.position = Position()
        g.setup_board()
        p = g.position
        p.start_history()
        before = p.key(), p.occurrences.copy()
        stats = {}
        _, move = search(p, node_limit=40, stats=stats)
        self.assertIn(move, p.legal_moves())
        self.assertLessEqual(stats['nodes'], 41)
        self.assertGreaterEqual(stats['depth'], 1)
        self.assertEqual(before, (p.key(), p.occurrences))

    def test_horizon_sees_opponents_immediate_lion_capture(self):
        p = position(turn=1)
        p.board[2][1] = Piece('giraffe', 1)
        score, _ = search(p, depth=0)
        self.assertGreater(score, 90000)

    def test_ai_chooses_try_win(self):
        p = Position(turn=1)
        p.board[2][0] = Piece('lion', 1)
        p.board[0][2] = Piece('lion', 0)
        _, move = search(p)
        child = p.clone()
        child.play(move)
        self.assertEqual((child.winner, child.reason), (1, 'try'))

    def test_capture_takes_priority_over_try_and_repetition(self):
        p = Position()
        p.board[1][0] = Piece('lion', 0)
        p.board[0][0] = Piece('lion', 1)
        child = p.clone()
        child.play(('move', 1, 0, 0, 0))
        p.occurrences[child.key()] = 2
        p.play(('move', 1, 0, 0, 0))
        self.assertEqual(p.reason, 'capture')


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requires a display or Xvfb')
class GuiTests(unittest.TestCase):
    def test_canvas_click_capture_and_scheduled_ai_for_both_orders(self):
        for first in (True, False):
            with self.subTest(first=first), patch('animal_shogi_strong.messagebox.askyesno', return_value=first):
                g = Game()
                try:
                    g.window.update()
                    self.assertEqual(g.position.occurrences[g.position.key()], 1)
                    if first:
                        g.canvas.event_generate('<Button-1>', x=120, y=200)
                        g.canvas.event_generate('<Button-1>', x=120, y=120)
                        self.assertEqual(g.board[1][1].owner, 0)
                        self.assertEqual(len(g.hands[0]), 1)
                    self.assertEqual(g.turn, 1)
                    deadline = time.monotonic() + 3
                    while g.turn == 1 and time.monotonic() < deadline:
                        g.window.update()
                        time.sleep(.01)
                    self.assertEqual(g.turn, 0)
                    self.assertFalse(g.position.finished)
                finally:
                    g.window.destroy()

    def test_gui_try_dialog_and_post_game_ai(self):
        with patch('animal_shogi_strong.messagebox.askyesno', return_value=True):
            g = Game()
        p = Position()
        p.board[1][0] = Piece('lion', 0)
        p.board[2][2] = Piece('lion', 1)
        g.position = p
        g.draw()
        g.window.update()
        with patch('animal_shogi_strong.messagebox.showinfo') as info:
            g.canvas.event_generate('<Button-1>', x=40, y=120)
            g.canvas.event_generate('<Button-1>', x=40, y=40)
            g.ai_move()
        self.assertEqual(p.reason, 'try')
        info.assert_called_once_with('Game Over', 'Player 1 wins! (Try)')

if __name__ == '__main__':
    unittest.main()
