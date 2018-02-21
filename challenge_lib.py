class Matcher:
  def __init__(self):
    pass
  
  def apply(self, enemyFleetId, enemyShips):
    raise NotImplementedError()

class AllMatcher:
  def __init__(self):
    pass

  def apply(self, enemyFleetId, enemyShips):
    return True

class AssertEnemyMatcher:
  def __init__(self, enemyCid: int):
    self.enemyCid = enemyCid

  def apply(self, enemyFleetId: int, enemyShips: int):
    for ship in enemyShips:
      if int(ship['shipCid']) == enemyCid:
        return True
    return False

class NodeRule:
  def __init__(self, rules):
    self.rules_ = list(rules)

  def apply(self, enemyFleetId, enemyShips):
    for rule in self.rules_:
      if rule[0].apply(enemyFleetId, enemyShips):
        return rule[1]
    return 0

class Strategy:
  def __init__(self, mapId, continuingNodes, nodeRules):
    self.mapId = mapId
    self.continuingNodes = continuingNodes
    self.nodeRules = nodeRules

strategy_601A = Strategy(601, [60101], {
  60102: NodeRule([(AllMatcher(), 5)])
})

activeStrategy = strategy_601A
