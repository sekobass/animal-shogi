"""Compare against the shipped 3-ply AI, swapping sides for six openings."""
import random, time, sys, types, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import animal_shogi_engine as new
from animal_shogi_strong import Game
old = types.ModuleType('baseline')
exec(subprocess.check_output(['git', 'show', '027608d:animal_shogi_engine.py'], text=True), old.__dict__)
rng=random.Random(43); wins=losses=draws=0; elapsed=[]; depths=[]
for opening in range(6):
 g=Game.__new__(Game);g.position=new.Position();g.setup_board();p=g.position;p.start_history()
 for _ in range(0 if opening == 0 else 4):
  if p.finished:break
  safe=[]
  for m in p.legal_moves():
   child=p.clone();child.play(m)
   score,_=new.search(child,depth=1,node_limit=None)
   if not child.finished and abs(score)<90000:safe.append(m)
  if not safe:break
  p.play(rng.choice(safe))
 if p.finished:continue
 for side in (0,1):
  q=p.clone()
  for ply in range(100):
   if q.finished:break
   if q.turn==side:
    stats={};start=time.monotonic();_,move=new.search(q.clone(),stats=stats)
    elapsed.append(time.monotonic()-start);depths.append(stats['depth'])
   else:_,move=old.search(q.clone())
   if move is None:break
   q.play(move)
  result='draw' if not q.finished or q.winner is None else ('win' if q.winner==side else 'loss')
  wins+=result=='win';losses+=result=='loss';draws+=result=='draw'
  print(opening,side,result,'plies',ply,flush=True)
print(dict(wins=wins,losses=losses,draws=draws,max_seconds=max(elapsed),average_seconds=sum(elapsed)/len(elapsed),depth_min=min(depths),depth_max=max(depths)),flush=True)
