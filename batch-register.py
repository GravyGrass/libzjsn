#!/usr/bin/python3
# encoding: UTF-8

import libzjsn

loginServer = 'login.jr.moefantasy.com'
aliveServers = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
aliveServers = [11, 12, 13, 14]

def gameServer(serverId):
  return 's{}.jr.moefantasy.com'.format(serverId)

def registerAndCreateCharacter(i, postfix):
  username = 'buildradar{}{}'.format(i, postfix)
  password = 'build_{}_123456'.format(i)
  (success, message) = libzjsn.register(loginServer, username, password, '雷达', '110101195001010033')
  if success:
    cookie = message
    return libzjsn.createCharacter(gameServer(i), cookie, '雷达{}{}'.format(i, postfix), 10006411)
  else:
    raise ValueError(message)

for i in aliveServers:
  print('Creating account on server {}'.format(i))
  status = registerAndCreateCharacter(i, 'a')
  print(status == 1 and 'success' or 'failure')
  status = registerAndCreateCharacter(i, 'b')
  print(status == 1 and 'success' or 'failure')
