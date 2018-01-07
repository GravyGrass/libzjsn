import logging
import os
import time

import libzjsn

from libzjsn import writeDebugJSON

logger = logging.getLogger('libzjsn.BasicClient')

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
