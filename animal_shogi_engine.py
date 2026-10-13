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
        self._play_legal(move)

    def _play_legal(self, move):
        # Internal fast path: caller must obtain the move from legal_moves().
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


VALUES = {'lion': 0, 'elephant': 300, 'giraffe': 350, 'chick': 110}
WIN = 100000


def evaluate(position):
    """CPU-centric material, mobility, promotion and lion safety."""
    score = 0
    for owner in (0, 1):
        value = sum(VALUES[p.name] * 1.15 for p in position.hands[owner])
        for r, row in enumerate(position.board):
            for c, p in enumerate(row):
                if p is None or p.owner != owner:
                    continue
                progress = 3 - r if owner == 0 else r
                value += 320 if p.promoted else VALUES[p.name]
                mobility = sum(0 <= r + dr < ROWS and 0 <= c + dc < COLS
                               and (position.board[r + dr][c + dc] is None
                                    or position.board[r + dr][c + dc].owner != owner)
                               for dr, dc in p.moves())
                value += mobility * 8
                if p.name == 'chick' and not p.promoted:
                    value += progress * 25
                if p.name == 'lion':
                    value += progress * 35
                    if position.attacked(r, c, 1 - owner):
                        value -= 1200 if position.turn != owner else 250
                    else:
                        value += 60
                elif position.attacked(r, c, 1 - owner):
                    value -= (320 if p.promoted else VALUES[p.name]) * .25
        score += value if owner == 1 else -value
    return score


def search(position, depth=10, alpha=float('-inf'), beta=float('inf'),
           node_limit=20000, stats=None):
    """Iterative deepening alpha-beta with a deterministic work budget.

    Scores are always from CPU/player 1's perspective. Repetition history is
    retained in every branch. Cached moves only affect ordering, never scores.
    """
    position.adjudicate_capture()
    nodes = 0
    completed = 0
    preferred = {}

    class BudgetExhausted(Exception):
        pass

    def ordered(state, moves):
        favored = preferred.get(state.key())
        def priority(move):
            score = 1000000 if move == favored else 0
            if move[0] == 'move':
                _, sr, sc, r, c = move
                piece, target = state.board[sr][sc], state.board[r][c]
                if target:
                    score += 500000 if target.name == 'lion' else 1000 + VALUES[target.name]
                if piece.name == 'lion' and r == (0 if piece.owner == 0 else 3):
                    score += 5000
                if piece.name == 'chick' and r == (0 if piece.owner == 0 else 3):
                    score += 800
            return score
        return sorted(moves, key=priority, reverse=True)

    def visit(state, remaining, low, high, ply):
        nonlocal nodes
        nodes += 1
        if node_limit is not None and nodes > node_limit:
            raise BudgetExhausted
        if state.finished:
            if state.winner is None:
                return 0, None
            return (WIN - ply) * (1 if state.winner == 1 else -1), None
        moves = state.legal_moves()
        if not moves:
            return evaluate(state), None
        if remaining == 0:
            # Do not miss a capture or safe try just beyond the horizon.
            for move in moves:
                if move[0] != 'move':
                    continue
                _, sr, sc, r, c = move
                target, piece = state.board[r][c], state.board[sr][sc]
                if ((target and target.name == 'lion') or
                    (piece.name == 'lion' and r == (0 if piece.owner == 0 else 3))):
                    child = state.clone()
                    child._play_legal(move)
                    if child.finished and child.winner == state.turn:
                        return (WIN - ply - 1) * (1 if state.turn == 1 else -1), None
            return evaluate(state), None
        maximizing = state.turn == 1
        best = float('-inf') if maximizing else float('inf')
        choice = None
        for move in ordered(state, moves):
            child = state.clone()
            child._play_legal(move)
            value, _ = visit(child, remaining - 1, low, high, ply + 1)
            if choice is None or (value > best if maximizing else value < best):
                best, choice = value, move
            if maximizing:
                low = max(low, best)
            else:
                high = min(high, best)
            if high <= low:
                break
        preferred[state.key()] = choice
        return best, choice

    if position.finished:
        result = (0 if position.winner is None else WIN * (1 if position.winner == 1 else -1), None)
    elif depth == 0:
        result = visit(position, 0, alpha, beta, 0)
    else:
        moves = position.legal_moves()
        result = (evaluate(position), moves[0] if moves else None)
        for current_depth in range(1, depth + 1):
            try:
                candidate = visit(position, current_depth, alpha, beta, 0)
            except BudgetExhausted:
                break
            result = candidate
            completed = current_depth
            if abs(result[0]) >= WIN - current_depth:
                break
    if stats is not None:
        stats.update(nodes=nodes, depth=completed)
    return result
