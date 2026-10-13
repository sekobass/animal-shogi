"""GUI-independent animal shogi rules and AI."""

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


