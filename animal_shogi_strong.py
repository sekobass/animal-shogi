# coding: utf-8

import tkinter as tk
from tkinter import messagebox

from animal_shogi_engine import CELL_SIZE, ROWS, COLS, Piece, Position, search

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
