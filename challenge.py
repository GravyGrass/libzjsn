import json
import logging
import os
import time
import traceback

import libzjsn

from challenge_lib import activeStrategy
from client import BasicClient, BattleSession, BattleWithBrokenShip
from libzjsn import writeDebugJSON as writeJSON

logging.basicConfig(level = logging.DEBUG)

libzjsn.loadConfig()
libzjsn.setSocketTimeout(60)

TARGET_LEVEL = 110

config = json.load(open('challenge.json', 'r'))
nodeRules = activeStrategy.nodeRules

def getExpProgress(shipResult):
  exp = 0
  if 'exp' in shipResult:
    exp = int(shipResult['exp'])
  needed = int(shipResult['nextLevelExpNeed'])
  return (exp, exp + needed)

def execute(client):
  session = BattleSession(client, config['fleetId'], activeStrategy.mapId)
  session.start()

  while session.currentNode in activeStrategy.continuingNodes:
    session.next()
    currentNodeId = session.currentNode
    enemyFleetId = session.enemyFleetId
    enemyShips = session.enemyShips
    if currentNodeId in nodeRules:
      if enemyShips:
        logging.info('Enemy ships:\n' + '\n'.join([ship['title'] for ship in enemyShips]))
      nodeRule = nodeRules[currentNodeId]
      formation = nodeRule.apply(enemyFleetId, enemyShips)
      if formation == 0:
        logging.info('No matching rule. Abort session.')
        return
      elif formation == -1:
        logging.info('Skipping required. Feature not implemented. Aborting.')
      else:
        assert(formation > 0)
        warReport = session.deal(formation)
        if warReport:
          logging.info('Self HP: ' + ' '.join([
              '{}/{}'.format(warReport.hpBeforeNightSelf[i], warReport.hpMaxSelf[i])
              for i in range(len(warReport.hpMaxSelf))]))
          logging.info('Enemy HP: ' + ' '.join([
              '{}/{}'.format(warReport.hpBeforeNightEnemy[i], warReport.hpMaxEnemy[i])
              for i in range(len(warReport.hpMaxEnemy))]))
          warResult = session.getWarResult(False)

          logging.info('Battle result level: %d', int(warResult['warResult']['resultLevel']))
          logging.info('Levels: %s', ', '.join([str(shipResult['level'])
              for shipResult in warResult['warResult']['selfShipResults']]))
          logging.info('Exp: %s', ', '.join(['{}/{}'.format(*getExpProgress(shipResult))
              for shipResult in warResult['warResult']['selfShipResults']]))
          logging.info('%d ships in repository', client.getShipCount())

          for shipResult in warResult['warResult']['selfShipResults']:
            if int(shipResult['level']) == TARGET_LEVEL:
              return 'One ship reached level {}'.format(TARGET_LEVEL)

          if 'drop500' in warResult and int(warResult['drop500']) == 1:
            return '500 drop reached'

def main():
  client = BasicClient(
      config['loginServer'],
      config['gameServer'],
      config['userName'],
      config['password'],
      debug = True)
  while True:
    try:
      message = execute(client)
      if message:
        logging.info('%s', message)
        break
      client.simulateMainScreen()
      time.sleep(1)
    except BattleWithBrokenShip as e:
      repairResult = client.issueCommand('/boat/instantRepairShips/[{}]/'.format(e.shipId), True)
      writeJSON('debugData/instantRepairShips.json', repairResult)
      time.sleep(2)
    except libzjsn.ServerError as e:
      if e.message == '参数错误':
        logging.info('Ignorable ServerError', exc_info = e)
      else:
        raise

main()
