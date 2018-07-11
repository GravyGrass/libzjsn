#!/usr/bin/python3

import argparse
import json
import logging
import os
import time
import traceback

import libzjsn

from challenge_lib import strategies
from client import BasicClient, BattleSession, BattleWithBrokenShip
from global_args import extra_args
from libzjsn import writeDebugJSON as writeJSON

parser = argparse.ArgumentParser()
parser.add_argument('--fleet-id', type = int, required = True)
parser.add_argument('--strategy', required = True)
args = parser.parse_args(extra_args)

logging.basicConfig(level = logging.DEBUG)

libzjsn.loadConfig()
libzjsn.setSocketTimeout(60)

TARGET_LEVEL = 110

config = json.load(open('challenge.json', 'r'))
activeStrategy = strategies[args.strategy]
nodeRules = activeStrategy.nodeRules

def getExpProgress(shipResult):
  exp = 0
  if 'exp' in shipResult:
    exp = int(shipResult['exp'])
  needed = int(shipResult['nextLevelExpNeed'])
  return (exp, exp + needed)

def execute(client):
  session = BattleSession(client, args.fleet_id, activeStrategy.mapId)
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
          
          if client.resources.spoils:
            logging.info('%d spoils', client.resources.spoils)
            if client.resources.spoils >= int(config['targetSpoils']):
              return 'Enough spoils for today'

def main():
  def makeClient():
    return BasicClient(
        config['loginServer'],
        config['gameServer'],
        config['userName'],
        config['password'],
        debug = True)
  while True:
    client = makeClient()
    try:
      while True:
        try:
          message = execute(client)
          if message:
            logging.info('%s', message)
            return
          client.simulateMainScreen()
          time.sleep(1)
        except BattleWithBrokenShip as e:
          repairResult = client.issueCommand('/boat/instantRepairShips/[{}]/'.format(e.shipId), True)
          writeJSON('instantRepairShips.json', repairResult)
          time.sleep(2.5)
        except libzjsn.ServerError as e:
          if e.message == '参数错误':
            logging.info('Ignorable ServerError', exc_info = e)
          else:
            raise
    except libzjsn.ServerError as e:
      if e.message in ['数据不存在', '正在出征中']:
        logging.info('Reload because of ServerError', exc_info = e)
      else:
        raise

main()
