import json
import logging
import os
import time
import traceback

import libzjsn

from client import BasicClient
from libzjsn import writeDebugJSON as writeJSON

logging.basicConfig(level = logging.DEBUG)

libzjsn.loadConfig()
libzjsn.setSocketTimeout(10)

TARGET_LEVEL = 110

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

with open('challenge.conf', 'r', encoding = 'UTF-8') as conf:
  LOGIN_SERVER, GAME_SERVER, USER_NAME, PASSWORD, FLEET_ID, MAP_ID, FORMATION_ID = [l.strip() for l in conf]
  FLEET_ID = int(FLEET_ID)
  MAP_ID = int(MAP_ID)
  FORMATION_ID = int(FORMATION_ID)

def execute(client):
  selfShips = client.getFleetDetails(FLEET_ID)
  if not selfShips:
    raise GameLogicError('Fleet {} is empty.'.format(FLEET_ID))
  
  for ship in selfShips:
    if libzjsn.isHalfBroken(ship):
      raise BattleWithBrokenShip(
          ship['id'], ship['shipCid'], ship['battleProps']['hp'], ship['battlePropsMax']['hp'])
  
  supplyResult = client.issueCommand('/boat/supplyBoats/[{}]/{}/{}/'.format(
      ','.join([str(ship['id']) for ship in selfShips]), MAP_ID, 0), True)
  writeJSON('debugData/supplyBoats.json', supplyResult)
  
  time.sleep(1)
  
  startingData = client.issueCommand('/pve/cha11enge/{}/{}/0/'.format(MAP_ID, FLEET_ID))
  writeJSON('debugData/cha11enge.{}.{}.json'.format(MAP_ID, FLEET_ID), startingData)
  assert(int(startingData['pveLevelEnd']) == 0)
  assert(int(startingData['status']) == 1)
  
  newNext = client.issueCommand('/pve/newNext/')
  writeJSON('debugData/newNext.json', newNext)
  currentNode = int(newNext['node'])
  
  time.sleep(1)
  
  spy = client.issueCommand('/pve/spy/')
  writeJSON('debugData/spy.json', spy)
  
  time.sleep(1)
  
  dealResult = client.issueCommand(
      '/pve/dealto/{}/{}/{}/'.format(currentNode, FLEET_ID, FORMATION_ID))
  writeJSON('debugData/dealto.{}.json'.format(currentNode), dealResult)
  
  dayWarReport = dealResult['warReport']
  hpBeforeNight = dayWarReport['hpBeforeNightWarSelf']
  logging.info('Self HP: ' + ', '.join([str(hp) for hp in hpBeforeNight]))
  
  time.sleep(20)
  
  warResult = client.issueCommand('/pve/getWarResult/0/', True)
  writeJSON('debugData/warResult.json', warResult)
  
  logging.info('Battle result level: %d', int(warResult['warResult']['resultLevel']))
  logging.info('Levels: %s', ', '.join([str(shipResult['level'])
      for shipResult in warResult['warResult']['selfShipResults']]))
  logging.info('Exp: %s', ', '.join([
      '{}/{}'.format(shipResult['exp'], shipResult['exp'] + shipResult['nextLevelExpNeed'])
      for shipResult in warResult['warResult']['selfShipResults']]))
  
  for shipResult in warResult['warResult']['selfShipResults']:
    if int(shipResult['level']) == TARGET_LEVEL:
      return 'One ship reached level {}'.format(TARGET_LEVEL)

def main():
  client = BasicClient(LOGIN_SERVER, GAME_SERVER, USER_NAME, PASSWORD, debug = True)
  while True:
    try:
      message = execute(client)
      if message:
        logging.info('%s', message)
        break
      time.sleep(1)
      client.simulateMainScreen()
      time.sleep(1)
    except BattleWithBrokenShip as e:
      repairResult = client.issueCommand('/boat/instantRepairShips/[{}]/'.format(e.shipId), True)
      writeJSON('debugData/instantRepairShips.json', repairResult)
      time.sleep(1)

main()
