import logging
import os
import time

import libzjsn

from libzjsn import MapNodeType, writeDebugJSON

logger = logging.getLogger('libzjsn.BasicClient')

class GameLogicError(libzjsn.Error):
  def __init__(self, message):
    self.message = message

class DangerousOperation(Exception):
  def __str__(self):
    return self.message

class BattleWithBrokenShip(DangerousOperation):
  def __init__(self, shipId, shipCid, hp, maxHp):
    self.shipId = shipId
    self.shipCid = shipCid
    self.hp = hp
    self.maxHp = maxHp
    self.message = 'Ship {} with cid = {} has low HP {}/{}'.format(shipId, shipCid, hp, maxHp)

class BasicClient:
  def __init__(self, loginServer, gameServer, username, password, debug = False):
    self._gameServer = gameServer
    logger.info('Logging in as %s', username)
    cookie, initGame, pveData, peventData, canBuy, bsea, userInfo, activeUserData, pveUserData, campaignUserData = libzjsn.fullLogin(
      loginServer, gameServer, username, password)
    logger.info('Login finished')
    if debug:
      os.makedirs('debugData', exist_ok = True)
      writeDebugJSON('debugData/initGame.json', initGame)
      writeDebugJSON('debugData/pveData.json', pveData)
      writeDebugJSON('debugData/peventData.json', peventData)
      writeDebugJSON('debugData/canBuy.json', canBuy)
      writeDebugJSON('debugData/bsea.json', bsea)
      writeDebugJSON('debugData/userInfo.json', userInfo)
      writeDebugJSON('debugData/activeUserData.json', activeUserData)
      writeDebugJSON('debugData/pveUserData.json', pveUserData)
      writeDebugJSON('debugData/campaignUserData.json', campaignUserData)
    self._cookie = cookie
    self._gatherShips(initGame)
    self._gatherFleets(initGame)
    self._processPveData(pveData)

  def _gatherShips(self, initGame):
    self.ships = {}

    userShipVO = initGame['userShipVO']
    for ship in userShipVO:
      shipId = int(ship['id'])
      logger.debug('Ship %d: %s(%s)', shipId, libzjsn.getCanonicalShipName(ship['shipCid']), ship['title'])
      self.ships[shipId] = ship

  def _gatherFleets(self, initGame):
    self.fleets = {}
    
    fleetVo = initGame['fleetVo']
    for fleet in fleetVo:
      fleetId = int(fleet['id'])
      logger.debug('Fleet %d: %s', fleetId, fleet['title'])
      self.fleets[fleetId] = fleet
  
  def _processPveData(self, pveData):
    self.pveLevels = {}
    self.pveNodes = {}

    for level in pveData['pveLevel']:
      self.pveLevels[int(level['id'])] = level
    for node in pveData['pveNode']:
      self.pveNodes[int(node['id'])] = node
  
  def _addNewShip(self, ship):
    shipId = int(ship['id'])
    assert(shipId not in self.ships)
    self.ships[shipId] = ship
  
  def _replaceShip(self, ship):
    shipId = int(ship['id'])
    assert(shipId in self.ships)
    self.ships[shipId] = ship
  
  def _processNewShipVO(self, newShipVO):
    for ship in newShipVO:
      self._addNewShip(ship)
  
  def _processShipVO(self, shipVO):
    for ship in shipVO:
      self._replaceShip(ship)
  
  def _processUpdateTaskVo(self, updateTaskVo):
    def conditionSatisfied(condition):
      return int(condition['finishedAmount']) >= int(condition['totalAmount'])
    
    for task in updateTaskVo:
      if all((conditionSatisfied(cond) for cond in task['condition'])):
        taskCid = int(task['taskCid'])
        self.getTaskAward(taskCid)
        time.sleep(1)
  
  def processGenericResponse(self, response):
    for key, data in response.items():
      if key == 'userVo':
        pass
      elif key == 'packageVo':
        pass
      elif key == 'shipVO' or key == 'shipVOs':
        self._processShipVO(data)
      elif key == 'newShipVO':
        self._processNewShipVO(data)
      elif key == 'updateTaskVo':
        self._processUpdateTaskVo(data)
      else:
        logger.debug('Unknown response key: %s', key)
  
  def getTaskAward(self, taskCid):
    return self.issueCommand('/task/getAward/{}/'.format(taskCid), True)
  
  def getShipCount(self):
    return len(self.ships)
  
  def getFleetDetails(self, fleetId):
    fleet = self.fleets[fleetId]
    return [self.ships[int(shipId)] for shipId in fleet['ships']]

  def simulateMainScreen(self):
    return libzjsn.simulateMainScreen(self._gameServer, self._cookie)
  
  def issueCommand(self, command, processResult = False):
    response = libzjsn.issueCommand(self._gameServer, command, self._cookie)
    if processResult:
      self.processGenericResponse(response)
    return response

class DayWarReport:
  def __init__(self, dayWarReport):
    self.canDoNightWar = int(dayWarReport['canDoNightWar']) != 0
    self.hpBeforeNightSelf = dayWarReport['hpBeforeNightWarSelf']
    self.hpBeforeNightEnemy = dayWarReport['hpBeforeNightWarEnemy']
    self.hpMaxSelf = [ship['hpMax'] for ship in dayWarReport['selfShips']]
    self.hpMaxEnemy = [ship['hpMax'] for ship in dayWarReport['enemyShips']]

class BattleSession:
  def __init__(self, client, fleetId, mapId):
    self._client = client
    self._fleetId = fleetId
    self._mapId = mapId

    self.currentNode = int(client.pveLevels[mapId]['initNodeId'])

    self.enemyFleetId = 0
    self.enemyShips = None

  def start(self):
    client = self._client
    fleetId = self._fleetId
    mapId = self._mapId

    self._detectBrokenShips(libzjsn.isHalfBroken)

    supplyResult = client.issueCommand('/boat/supplyBoats/[{}]/{}/{}/'.format(
        ','.join([str(ship['id']) for ship in self._getSelfShips()]), mapId, 0), True)
    writeDebugJSON('debugData/supplyBoats.json', supplyResult)
    time.sleep(1)

    startingData = client.issueCommand('/pve/cha11enge/{}/{}/0/'.format(mapId, fleetId))
    writeDebugJSON('debugData/cha11enge.{}.{}.json'.format(mapId, fleetId), startingData)
    assert(int(startingData['pveLevelEnd']) == 0)
    assert(int(startingData['status']) == 1)

  def next(self):
    self._detectBrokenShips(libzjsn.isBroken)

    newNext = self._client.issueCommand('/pve/newNext/')
    writeDebugJSON('debugData/newNext.json', newNext)
    self.currentNode = int(newNext['node'])
    self.enemyFleetId = 0
    self.enemyShips = None
    time.sleep(1)
    
    nodeType = int(self._client.pveNodes[self.currentNode]['nodeType'])
    if nodeType not in [MapNodeType.RESOURCE, MapNodeType.IDLE, MapNodeType.TOLL]:
      spy = self._client.issueCommand('/pve/spy/')
      writeDebugJSON('debugData/spy.json', spy)
      self.enemyFleetId = int(spy['enemyVO']['enemyFleet']['id'])
      self.enemyShips = spy['enemyVO']['enemyShips']
      time.sleep(1)

  def deal(self, formationId):
    dealResult = self._client.issueCommand(
        '/pve/dealto/{}/{}/{}/'.format(self.currentNode, self._fleetId, formationId))
    writeDebugJSON('debugData/dealto.{}.json'.format(self.currentNode), dealResult)

    if 'warReport' in dealResult:
      dayWarReport = dealResult['warReport']
      time.sleep(20)
      return DayWarReport(dayWarReport)
    else:
      return None

  def getWarResult(self, nightWar):
    warResult = self._client.issueCommand(
        '/pve/getWarResult/{}/'.format(1 if nightWar else 0),
        True)
    writeDebugJSON('debugData/warResult.json', warResult)
    time.sleep(1)
    return warResult

  def _detectBrokenShips(self, detector):
    selfShips = self._getSelfShips()

    for ship in selfShips:
      if libzjsn.isHalfBroken(ship):
        raise BattleWithBrokenShip(
            ship['id'], ship['shipCid'], ship['battleProps']['hp'], ship['battlePropsMax']['hp'])

  def _getSelfShips(self):
    selfShips = self._client.getFleetDetails(self._fleetId)
    if not selfShips:
      raise GameLogicError('Fleet {} is empty.'.format(fleetId))
    return selfShips
