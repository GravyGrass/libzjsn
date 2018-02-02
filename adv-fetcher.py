#!/usr/bin/python3

import os
import sched
import sqlite3
import sys
import time
import traceback

import libzjsn

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from queue import Queue
from threading import Thread

FLAG_LOG_RAW = False

fetchedLogs = Queue()

def createDb(name):
  conn = sqlite3.connect(name)
  with closing(conn):
    with conn:
      conn.execute('CREATE TABLE IF NOT EXISTS build_results (server INTEGER NOT NULL, ID INTEGER NOT NULL, UID INTEGER NOT NULL, username STRING NOT NULL, time INTEGER NOT NULL, CID INTEGER NOT NULL, type INTEGER NOT NULL, oil INTEGER NOT NULL, ammo INTEGER NOT NULL, steel INTEGER NOT NULL, aluminium INTEGER NOT NULL, CONSTRAINT primary_key PRIMARY KEY (server, ID) ON CONFLICT IGNORE );')

def insert(conn, entries):
  with conn:
    return conn.executemany('INSERT OR IGNORE INTO build_results (server, ID, UID, username, time, CID, type, oil, ammo, steel, aluminium) VALUES (?,?,?,?,?,?,?,?,?,?,?);', entries).rowcount

def writeDbJob(dbName):
  conn = sqlite3.connect(dbName)
  with closing(conn):
    conn.execute('PRAGMA busy_timeout = 1200000;')
    while True:
      serverId, category, timestamp, entries = fetchedLogs.get()
      fetchedLogs.task_done()
      if category and timestamp and entries:
        try:
          sys.stderr.write('WriteDb: {:02d}.{}.{}\n'.format(serverId, category, timestamp))
          numNewLogs = insert(conn, entries)
          sys.stderr.write('Success: {:02d}.{}.{}, {} new entries\n'.format(serverId, category, timestamp, numNewLogs))
        except:
          traceback.print_exc()

def fetchLog(serverId, gameServer, cookie, category):
  try:
    timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
    sys.stderr.write('Request: {:02d}.{}.{}\n'.format(serverId, category, timestamp))
    command = '/dock/getBuild{}Log/'.format(category)
    request = libzjsn.makeHTTPRequestEx('GET', gameServer, command, cookie)
    response = libzjsn.sendRawHTTPRequest(gameServer, request)
    j = libzjsn.decodeHTTPResponse(response)
    if FLAG_LOG_RAW:
      decompressed = libzjsn.decompressHTTPResponse(response)
      fileName = 'logs/{:02d}.{}.{}.log'.format(serverId, category, timestamp)
      with closing(open(fileName, 'wb')) as f:
        f.write(decompressed)
    if 'log' not in j:
      sys.stderr.write('Failure: {:02d}.{}.{}\n'.format(serverId, category, timestamp))
      return
    entries = [(serverId, e['id'], e['uid'], e['username'], e['createTime'], e['cid'], e['type'], e['res']['oil'], e['res']['ammo'], e['res']['steel'], e['res']['aluminium']) for e in j['log']]
    fetchedLogs.put((serverId, category, timestamp, entries[:30]))
    sys.stderr.write('Enqueue: {:02d}.{}.{}\n'.format(serverId, category, timestamp))
  except:
    traceback.print_exc()

def oneServerJob(serverId, category):
  loginServer = 'login.jr.moefantasy.com'
  gameServer = 's{}.jr.moefantasy.com'.format(serverId)

  user1 = 'buildradar{}a'.format(serverId)
  password1 = 'build_{}_123456'.format(serverId)

  user2 = 'buildradar{}b'.format(serverId)
  password2 = 'build_{}_123456'.format(serverId)

  refreshPeriod = 43200
  fetchPeriod = 5

  fetcherPool = ThreadPoolExecutor(10)

  scheduler = sched.scheduler()
  cookie = None

  def updateCookie():
    nonlocal cookie, user1, user2, password1, password2
    scheduler.enter(refreshPeriod, 0, updateCookie)
    while True:
      try:
        sys.stderr.write('Login as {}:{}\n'.format(user1, password1))
        cookie = libzjsn.login(loginServer, gameServer, user1, password1)
        break
      except:
        traceback.print_exc()
        time.sleep(5)
    sys.stderr.write('Login success\n')
    user1, user2 = user2, user1
    password1, password2 = password2, password1

  def launchFetcher():
    scheduler.enter(fetchPeriod, 0, launchFetcher)
    if cookie:
      fetcherPool.submit(fetchLog, serverId, gameServer, cookie, category)

  updateCookie()
  launchFetcher()
  scheduler.run()

def main():
  category = sys.argv[1]
  dbName = sys.argv[2]

  timeout = 5
  libzjsn.setSocketTimeout(timeout)

  createDb(dbName)
  writeDbThread = Thread(target = writeDbJob, name = 'WriteDbThread', args = (dbName,), daemon = True)
  writeDbThread.start()
  
  for serverId in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
    oneServerThread = Thread(target = oneServerJob, name = 'OneServerThread{}'.format(serverId), args = (serverId, category), daemon = True)
    oneServerThread.start()
  
  while True:
    time.sleep(5)
    print('Alive')

if __name__ == '__main__':
  main()
