# coding: utf-8

import tkinter as tk
from tkinter import messagebox

CELL_SIZE = 80
ROWS = 4
COLS = 3

EMOJIS = {
    'lion': '\U0001F981',  # 🦁
    'elephant': '\U0001F418',
    'giraffe': '\U0001F992',
    'chick': '\U0001F424',
    'hen': '\U0001F414',
}

class Piece:
    def __init__(self, name, owner, promoted=False):
        self.name = name
        self.owner = owner  # 0: bottom, 1: top
        self.promoted = promoted

    @property
    def display(self):
        if self.name == 'chick' and self.promoted:
            return EMOJIS['hen']
        return EMOJIS[self.name]

    def moves(self):
        forward = -1 if self.owner == 0 else 1
        if self.name == 'lion':
            return [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        if self.name == 'giraffe':
            return [(1,0), (-1,0), (0,1), (0,-1)]
        if self.name == 'elephant':
            return [(1,1), (1,-1), (-1,1), (-1,-1)]
        if self.name == 'chick':
            if self.promoted:
                if self.owner == 0:
                    return [(-1,0), (-1,-1), (-1,1), (0,-1), (0,1), (1,0)]
                else:
                    return [(1,0), (1,-1), (1,1), (0,-1), (0,1), (-1,0)]
            else:
                return [(forward,0)]
        return []

class Position:
    """Shared rule state used by both the GUI and the search."""

    def __init__(self, board=None, hands=None, turn=0):
        self.board = board if board is not None else [[None] * COLS for _ in range(ROWS)]
        self.hands = hands if hands is not None else {0: [], 1: []}
        self.turn = turn
        self.winner = None
        self.reason = None
        self.occurrences = {}

    @property
    def finished(self):
        return self.reason is not None

    def key(self):
        """Repetition includes side to move and hand counts, not hand order."""
        board = tuple((p.name, p.owner, p.promoted) if p else None
                      for row in self.board for p in row)
        hands = tuple(tuple(sorted(p.name for p in self.hands[owner]))
                      for owner in (0, 1))
        return board, hands, self.turn

    def start_history(self):
        self.occurrences = {self.key(): 1}

    def attacked(self, r, c, by_owner):
        # Check geometric attacks: self-check is allowed in animal shogi.
        return any(p and p.owner == by_owner and (r - sr, c - sc) in p.moves()
                   for sr, row in enumerate(self.board) for sc, p in enumerate(row))

    def clone(self):
        def copy_piece(p):
            return Piece(p.name, p.owner, p.promoted) if p else None
        result = Position([[copy_piece(p) for p in row] for row in self.board],
                          {owner: [copy_piece(p) for p in pieces]
                           for owner, pieces in self.hands.items()}, self.turn)
        result.winner, result.reason = self.winner, self.reason
        result.occurrences = self.occurrences.copy()
        return result

    def adjudicate_capture(self):
        if self.finished:
            return
        lions = {p.owner for row in self.board for p in row
                 if p and p.name == 'lion'}
        if len(lions) == 1:
            self.winner = next(iter(lions))
            self.reason = 'capture'

    def legal_moves(self):
        self.adjudicate_capture()
        if self.finished:
            return []
        moves = []
        for r, row in enumerate(self.board):
            for c, p in enumerate(row):
                if p is None or p.owner != self.turn:
                    continue
                for dr, dc in p.moves():
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS:
                        target = self.board[nr][nc]
                        if target is None or target.owner != self.turn:
                            moves.append(('move', r, c, nr, nc))
        for idx, p in enumerate(self.hands[self.turn]):
            if p.name == 'lion':
                continue
            for r in range(ROWS):
                for c in range(COLS):
                    if self.board[r][c] is None:
                        moves.append(('drop', idx, r, c))
        return moves

    def play(self, move):
        if move not in self.legal_moves():
            raise ValueError('Illegal move or finished game')
        if not self.occurrences:
            self.start_history()
        player = self.turn
        if move[0] == 'move':
            _, sr, sc, r, c = move
            piece, target = self.board[sr][sc], self.board[r][c]
            self.board[sr][sc] = None
            self.board[r][c] = piece
            if target:
                if target.name == 'lion':
                    self.winner, self.reason = player, 'capture'
                else:
                    self.hands[player].append(Piece(target.name, player))
            if piece.name == 'chick' and r == (0 if player == 0 else ROWS - 1):
                piece.promoted = True
            if (not self.finished and piece.name == 'lion'
                    and r == (0 if player == 0 else ROWS - 1)
                    and not self.attacked(r, c, 1 - player)):
                self.winner, self.reason = player, 'try'
        else:
            _, idx, r, c = move
            piece = self.hands[player].pop(idx)
            self.board[r][c] = Piece(piece.name, player)
        self.turn = 1 - player
        key = self.key()
        self.occurrences[key] = self.occurrences.get(key, 0) + 1
        if not self.finished and self.occurrences[key] >= 3:
            self.reason = 'repetition'


def evaluate(position):
    values = {'lion': 1000, 'elephant': 5, 'giraffe': 5, 'chick': 1}
    total = 0
    for r, row in enumerate(position.board):
        for p in row:
            if p:
                value = 3 if p.promoted else values[p.name]
                if p.name == 'chick' and not p.promoted:
                    value += ROWS - r if p.owner == 0 else r + 1
                total += value if p.owner == 1 else -value
    for owner, pieces in position.hands.items():
        for p in pieces:
            total += values[p.name] if owner == 1 else -values[p.name]
    return total


def search(position, depth=3, alpha=float('-inf'), beta=float('inf')):
    position.adjudicate_capture()
    if position.finished:
        score = 0 if position.winner is None else (10000 + depth) * (1 if position.winner == 1 else -1)
        return score, None
    moves = position.legal_moves()
    if depth == 0 or not moves:
        return evaluate(position), None
    maximizing = position.turn == 1
    best = float('-inf') if maximizing else float('inf')
    choice = None
    for move in moves:
        child = position.clone()
        child.play(move)
        score, _ = search(child, depth - 1, alpha, beta)
        if choice is None or (score > best if maximizing else score < best):
            best, choice = score, move
        if maximizing:
            alpha = max(alpha, best)
        else:
            beta = min(beta, best)
        if beta <= alpha:
            break
    return best, choice


class Game:
    def __init__(self):
        self.position = Position()
        self.ai_callback = None
        self.selected = None  # (row,col) or ('hand', index)
        self.window = tk.Tk()
        self.window.title('Animal Shogi (Strong AI)')

        # extra space at the bottom for player's hand
        self.hand_size = CELL_SIZE // 2
        height = ROWS * CELL_SIZE + self.hand_size
        # create the drawing canvas before calling pack
        self.canvas = tk.Canvas(self.window, width=COLS * CELL_SIZE, height=height)

        self.canvas.pack()
        self.canvas.bind('<Button-1>', self.on_click)
        self.setup_board()
        # allow player to choose to play second
        if not messagebox.askyesno('Turn Order', 'Play first? (Yes: first, No: second)'):
            self.turn = 1
        self.position.start_history()
        self.draw()
        if self.turn == 1:
            self.ai_callback = self.window.after(500, self.ai_move)

    @property
    def board(self):
        return self.position.board

    @property
    def hands(self):
        return self.position.hands

    @property
    def turn(self):
        return self.position.turn

    @turn.setter
    def turn(self, value):
        self.position.turn = value

    def ai_move(self):
        self.ai_callback = None
        self.position.adjudicate_capture()
        if self.position.finished or self.turn != 1:
            return
        _, choice = search(self.position.clone())
        if choice is not None:
            self.make_move(choice)

    def finish_game(self):
        if self.ai_callback is not None:
            self.window.after_cancel(self.ai_callback)
            self.ai_callback = None
        if self.position.winner is None:
            text = 'Draw! (Threefold repetition)'
        else:
            text = 'Computer wins!' if self.position.winner == 1 else 'Player 1 wins!'
            if self.position.reason == 'try':
                text += ' (Try)'
        messagebox.showinfo('Game Over', text)
        self.window.destroy()

    def make_move(self, move):
        self.position.play(move)
        self.selected = None
        self.draw()
        if self.position.finished:
            self.finish_game()
        else:
            self.end_turn()

    def setup_board(self):
        # Player 1 (bottom)
        self.board[3][0] = Piece('giraffe', 0)
        self.board[3][1] = Piece('lion', 0)
        self.board[3][2] = Piece('elephant', 0)
        self.board[2][1] = Piece('chick', 0)
        # Player 2 (top)
        self.board[0][0] = Piece('elephant', 1)
        self.board[0][1] = Piece('lion', 1)
        self.board[0][2] = Piece('giraffe', 1)
        self.board[1][1] = Piece('chick', 1)

    def draw(self):
        self.canvas.delete('all')
        for r in range(ROWS):
            for c in range(COLS):
                x1 = c * CELL_SIZE
                y1 = r * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE
                color = '#ffe0e0' if (r + c) % 2 == 0 else '#e0e0ff'
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)
                piece = self.board[r][c]
                if piece:
                    self.canvas.create_text(x1 + CELL_SIZE/2, y1 + CELL_SIZE/2,
                                             text=piece.display, font=('Arial', 30))

        # draw player's captured pieces at the bottom
        for i, piece in enumerate(self.hands[0]):
            x = i * self.hand_size + self.hand_size/2
            y = ROWS * CELL_SIZE + self.hand_size/2
            self.canvas.create_text(x, y, text=piece.display, font=('Arial', 20))

        if self.selected:
            if self.selected[0] == 'hand':
                i = self.selected[1]
                x1 = i * self.hand_size
                y1 = ROWS * CELL_SIZE
                x2 = x1 + self.hand_size
                y2 = y1 + self.hand_size
                self.canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=3)
            else:
                r, c = self.selected
                x1 = c * CELL_SIZE
                y1 = r * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=3)


    def in_bounds(self, r, c):
        return 0 <= r < ROWS and 0 <= c < COLS

    def legal_moves(self, r, c, piece):
        if not self.in_bounds(r, c) or self.board[r][c] is not piece:
            return []
        return [(mv[3], mv[4]) for mv in self.position.legal_moves()
                if mv[0] == 'move' and mv[1:3] == (r, c)]

    def on_click(self, event):
        if self.position.finished or self.turn != 0 or event.x < 0 or event.y < 0:
            return
        if event.y >= ROWS * CELL_SIZE:
            index = event.x // self.hand_size
            if event.y < ROWS * CELL_SIZE + self.hand_size and index < len(self.hands[0]):
                self.selected = ('hand', index)
                self.draw()
            return
        c, r = event.x // CELL_SIZE, event.y // CELL_SIZE
        if not self.in_bounds(r, c):
            return
        if self.selected:
            if self.selected[0] == 'hand':
                move = ('drop', self.selected[1], r, c)
            else:
                move = ('move', *self.selected, r, c)
            self.selected = None
            if move in self.position.legal_moves():
                self.make_move(move)
                return
        else:
            piece = self.board[r][c]
            if piece and piece.owner == self.turn:
                self.selected = (r, c)
        self.draw()

    def end_turn(self):
        # Position.play already switches the turn; never advance after game over.
        if not self.position.finished and self.turn == 1:
            self.ai_callback = self.window.after(500, self.ai_move)

    def run(self):
        self.window.mainloop()

if __name__ == '__main__':
    Game().run()
