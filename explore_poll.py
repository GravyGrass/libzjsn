#!/usr/bin/python3

import json
import logging
import os
import time
import traceback

import libzjsn

from libzjsn import writeDebugJSON as writeJSON

logging.basicConfig(level = logging.INFO)

libzjsn.loadConfig()
libzjsn.setSocketTimeout(10)

with open('explore_poll.conf', 'r', encoding = 'UTF-8') as conf:
  LOGIN_SERVER, GAME_SERVER, USER_NAME, PASSWORD, POLL_INTERVAL = [l.strip() for l in conf]
  POLL_INTERVAL = int(POLL_INTERVAL)

def pollOnce():
  print('Logging in...')
  cookie, initGame, pveData, peventData, canBuy, bsea, userInfo, activeUserData, pveUserData, campaignUserData = libzjsn.fullLogin(
      LOGIN_SERVER, GAME_SERVER, USER_NAME, PASSWORD)
  print('Login finished.')
  writeJSON('initGame.json', initGame)
  writeJSON('pveData.json', pveData)
  writeJSON('peventData.json', peventData)
  writeJSON('canBuy.json', canBuy)
  writeJSON('bsea.json', bsea)
  writeJSON('userInfo.json', userInfo)
  writeJSON('activeUserData.json', activeUserData)
  writeJSON('pveUserData.json', pveUserData)
  writeJSON('campaignUserData.json', campaignUserData)
  
  serverTime = int(initGame['systime'])
  exploreLevels = initGame['pveExploreVo']['levels']
  exploreLevels = sorted(exploreLevels, key = lambda x: int(x['exploreId']))
  
  for level in exploreLevels:
    exploreId = int(level['exploreId'])
    fleetId = int(level['fleetId'])
    endTime = int(level['endTime'])
    if endTime >= serverTime:
      print('Explore {}, fleet {}: unfinished.'.format(exploreId, fleetId))
    else:
      print('Explore {}, fleet {}: finished.'.format(exploreId, fleetId))
      exploreResult = libzjsn.getExploreResult(GAME_SERVER, exploreId, cookie)
      writeJSON('exploreResult.{}.json'.format(exploreId), exploreResult)
      startExploreResult = libzjsn.startExplore(GAME_SERVER, fleetId, exploreId, cookie)
      writeJSON('exploreStart.{}.json'.format(exploreId), startExploreResult)

def main():
  while True:
    try:
      print(time.strftime('%Y-%m-%d %H:%M:%S polling start.'))
      pollOnce()
    except:
      traceback.print_exc()
    time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
  main()
