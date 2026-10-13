"""Generate a single HTML file with the same Python rules as the desktop game."""
from pathlib import Path
import json
root = Path(__file__).resolve().parents[1]
html = (root / 'web/template.html').read_text()
engine = (root / 'animal_shogi_engine.py').read_text()
initial = '''
p = Position()
p.board[3][0] = Piece('giraffe', 0)
p.board[3][1] = Piece('lion', 0)
p.board[3][2] = Piece('elephant', 0)
p.board[2][1] = Piece('chick', 0)
p.board[0][0] = Piece('elephant', 1)
p.board[0][1] = Piece('lion', 1)
p.board[0][2] = Piece('giraffe', 1)
p.board[1][1] = Piece('chick', 1)
'''
bridge = '''
import json
def snapshot():
    return json.dumps(dict(board=[[dict(name=q.name, owner=q.owner, promoted=q.promoted) if q else None for q in row] for row in p.board], hands=[len(p.hands[0]),len(p.hands[1])], hand=[q.name for q in p.hands[0]], turn=p.turn, winner=p.winner, reason=p.reason, moves=p.legal_moves()),ensure_ascii=False)
def restart(first):
    global p
    exec(INITIAL, globals())
    p.turn = 0 if first else 1
    p.start_history()
def play_json(move):
    p.play(tuple(json.loads(move)))
def ai():
    if not p.finished and p.turn == 1:
        _, move = search(p.clone())
        if move is not None: p.play(move)
'''
code = engine + '\nINITIAL = '+repr(initial)+'\n'+bridge
out = root / 'dist'
out.mkdir(exist_ok=True)
(out/'animal-shogi.html').write_text(html.replace('__PYTHON__', json.dumps(code,ensure_ascii=False).replace('</','<\\/')))
