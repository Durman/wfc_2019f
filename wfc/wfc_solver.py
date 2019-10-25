import numpy

class Contradiction(Exception):
  """Solving could not proceed without backtracking/restarting."""
  pass

def makeWave(n, w, h, ground=None):
  wave = numpy.ones((n, w, h),dtype=bool)
  if ground is not None:
    wave[:,:,h-1] = 0
    wave[ground,:,h-1] = 1
  print(wave)
  return wave

def makeAdj(adjLists):
  adjMatrices = {}
  num_patterns = len(list(adjLists.values())[0])
  for d in adjLists:
    m = numpy.zeros((num_patterns,num_patterns),dtype=bool)
    for i, js in enumerate(adjLists[d]):
      for j in js:
        m[i,j] = 1
    adjMatrices[d] = m
  print(adjMatrices)
  return adjMatrices


######################################
# Location Heuristics

def makeEntropyLocationHeuristic(preferences):
  def entropyLocationHeuristic(wave):
    unresolved_cell_mask = (numpy.count_nonzero(wave, axis=0) > 1)
    cell_weights = numpy.where(unresolved_cell_mask, preferences + numpy.count_nonzero(wave, axis=0), numpy.inf)
    row, col = numpy.unravel_index(numpy.argmin(cell_weights), cell_weights.shape)
    return [row, col]
  return entropyLocationHeuristic


def lexicalLocationHeuristic(wave):
  unresolved_cell_mask = (numpy.count_nonzero(wave, axis=0) > 1)
  cell_weights = numpy.where(unresolved_cell_mask,  numpy.count_nonzero(wave, axis=0), numpy.inf)
  row, col = numpy.unravel_index(numpy.argmin(cell_weights), cell_weights.shape)
  return [row, col]

#####################################
# Pattern Heuristics

def lexicalPatternHeuristic(weights):
  return numpy.nonzero(weights)[0][0]



#####################################
# Solver

def propagate(wave, adj, periodic=False):
  last_count = wave.sum()

  while True:
    supports = {}
    if periodic:
      padded = numpy.pad(wave,((0,0),(1,1),(1,1)), mode='wrap')
    else:
      padded = numpy.pad(wave,((0,0),(1,1),(1,1)), mode='constant',constant_values=True)

    for d in adj:
      dx,dy = d
      shifted = padded[:,1+dx:1+wave.shape[1]+dx,1+dy:1+wave.shape[2]+dy]
      supports[d] = numpy.einsum('pwh,pq->qwh', shifted, adj[d]) > 0

    for d in adj:
      wave *= supports[d]

    if wave.sum() == last_count:
      break
    else:
      last_count = wave.sum()

  if wave.sum() == 0:
    raise Contradiction


def observe(wave, locationHeuristic, patternHeuristic):
  i,j = locationHeuristic(wave)
  pattern = patternHeuristic(wave[:,i,j])
  return pattern, i, j

def run(wave, adj, locationHeuristic, patternHeuristic, periodic=False, backtracking=False, onBacktrack=None, onChoice=None, checkFeasible=None):
  if checkFeasible:
    if not checkFeasible(wave):
      raise Contradiction
  original = wave.copy()
  propagate(wave, adj, periodic=periodic)
  try:
    pattern, i, j = observe(wave, locationHeuristic, patternHeuristic) 
    if onChoice:
      onChoice(pattern, i, j)
    wave[:, i, j] = False
    wave[pattern, i, j] = True
    propagate(wave, adj, periodic=periodic)
    if wave.sum() > wave.shape[1] * wave.shape[2]:
      return run(wave, adj, locationHeuristic, patternHeuristic, periodic, backtracking, onBacktrack)
    else:
      return numpy.argmax(wave, 0)
  except Contradiction:
    if backtracking:
      if onBacktrack:
        onBacktrack()
      wave = original
      wave[pattern, i, j] = False
      return run(wave, adj, locationHeuristic, patternHeuristic, periodic, backtracking, onBacktrack, checkFeasible)
    else:
      raise

#############################
# Tests

def test_makeWave():
  wave = makeWave(3, 10, 20, ground=-1)
  assert wave.sum() == (10*20*3 - 2*10)
  assert wave[2,5,19] == True
  assert wave[1,5,19] == False

def test_entropyLocationHeuristic():
    wave = numpy.ones((5, 3, 4), dtype=bool) # everthing is possible
    wave[1:,0, 0] = False # first cell is fully observed
    wave[4, :, 2] = False
    preferences = numpy.ones((3, 4), dtype=float) * 0.5
    preferences[1, 2] = 0.3
    preferences[1, 1] = 0.1
    heu = makeEntropyLocationHeuristic(preferences)
    result = heu(wave)
    assert [1, 2] == result

def test_observe():

  my_wave = numpy.ones((5, 3, 4), dtype=bool)
  my_wave[0,1,2] = False

  def locHeu(wave):
    assert numpy.array_equal(wave, my_wave)
    return 1,2
  def patHeu(weights):
    assert numpy.array_equal(weights, my_wave[:,1,2])
    return 3

  assert observe(my_wave,
                 locationHeuristic=locHeu,
                 patternHeuristic=patHeu) == (3,1,2)

def test_propagate():
  wave = numpy.ones((3,3,4),dtype=bool)
  adjLists = {}
  # checkerboard #0/#1 or solid fill #2
  adjLists[(+1,0)] = adjLists[(-1,0)] = adjLists[(0,+1)] = adjLists[(0,-1)] = [[1],[0],[2]]
  wave[:,0,0] = False
  wave[0,0,0] = True
  adj = makeAdj(adjLists)
  propagate(wave, adj, periodic=False)
  expected_result = numpy.array([[[ True, False,  True, False],
          [False,  True, False,  True],
          [ True, False,  True, False]],
        [[False,  True, False,  True],
          [ True, False,  True, False],
          [False,  True, False,  True]],
        [[False, False, False, False],
          [False, False, False, False],
          [False, False, False, False]]])
  assert numpy.array_equal(wave, expected_result)


def test_run():
  wave = makeWave(3,3,4)
  adjLists = {}
  adjLists[(+1,0)] = adjLists[(-1,0)] = adjLists[(0,+1)] = adjLists[(0,-1)] = [[1],[0],[2]]
  adj = makeAdj(adjLists)

  first_result = run(wave.copy(),
      adj,
      locationHeuristic=lexicalLocationHeuristic,
      patternHeuristic=lexicalPatternHeuristic,
      periodic=False)

  expected_first_result = numpy.array([[0, 1, 0, 1],[1, 0, 1, 0],[0, 1, 0, 1]])

  assert numpy.array_equal(first_result, expected_first_result)

  event_log = []
  def onChoice(pattern, i, j):
    event_log.append((pattern,i,j))
  def onBacktrack():
    event_log.append('backtrack')

  second_result = run(wave.copy(),
      adj,
      locationHeuristic=lexicalLocationHeuristic,
      patternHeuristic=lexicalPatternHeuristic,
      periodic=True,
      backtracking=True,
      onChoice=onChoice,
      onBacktrack=onBacktrack)

  expected_second_result = numpy.array([[2, 2, 2, 2],[2, 2, 2, 2],[2, 2, 2, 2]])

  assert numpy.array_equal(second_result, expected_second_result)
  assert event_log == [(0, 0, 0), 'backtrack']

  def explode(wave):
    if wave.sum() < 20:
      raise Infeasible

  try:
    result = run(wave.copy(),
        adj,
        locationHeuristic=lexicalLocationHeuristic,
        patternHeuristic=lexicalPatternHeuristic,
        periodic=True,
        backtracking=True,
        checkFeasible=explode)
    print(result)
    happy = False
  except Contradiction:
    happy = True

  assert happy

from pycallgraph import PyCallGraph
from pycallgraph.output import GraphvizOutput

if __name__ == "__main__":
  with PyCallGraph(output=GraphvizOutput()):
    test_makeWave()
    test_entropyLocationHeuristic()
    test_observe()
    test_propagate()
    test_run()

