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
      if int(ship['shipCid']) == self.enemyCid:
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

strategies = {
  '201Boss': Strategy(201, [20101, 20103, 20105], {
    20103: NodeRule([(AllMatcher(), 1)]),
    20105: NodeRule([(AllMatcher(), 1)]),
    20107: NodeRule([(AssertEnemyMatcher(20100003), 2)])
  }),
  '601A': Strategy(601, [60101], {
    60102: NodeRule([(AllMatcher(), 5)])
  }),
  '701A': Strategy(701, [70101], {
    70102: NodeRule([(AllMatcher(), 5)])
  })
}
