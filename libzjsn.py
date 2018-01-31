import base64
import collections
import hashlib
import json
import logging
import re
import socket
import time
import urllib.parse
import uuid
import zlib

client_version = '3.5.0'

logger = logging.getLogger('libzjsn')

initConfig = None
shipByCid = None

def loadConfig(path = 'init.json'):
  global initConfig
  global shipByCid
  with open(path, 'r', encoding = 'UTF-8') as configFile:
    initConfig = json.load(configFile, object_pairs_hook=collections.OrderedDict)
  
  shipByCid = {}
  for ship in initConfig['shipCardWu']:
    cid = int(ship['cid'])
    shipByCid[cid] = ship

class Error(Exception):
  def __str__(self):
    return self.message

class HTTPError(Error):
  def __init__(self, code, message):
    self.code = code
    self.message = message
  
  def __str__(self):
    return '{} {}'.format(self.code, self.message)

class ServerError(Error):
  def __init__(self, errorCode):
    self.errorCode = int(errorCode)
    eid = str(self.errorCode)
    messageDict = initConfig['errorCode']
    if eid in messageDict:
      self.message = messageDict[eid]
    else:
      self.message = 'Unknown error {}'.format(eid)

class LoginError(Error):
  def __init__(self, message):
    self.message = message

def setSocketTimeout(timeout):
  socket.setdefaulttimeout(timeout)

def writeDebugJSON(path, content):
  with open(path, 'w', encoding = 'UTF-8', newline = '\n') as f:
    json.dump(content, f, ensure_ascii = False, indent = 2)

def sendRawHTTPRequest(host, request):
  with socket.create_connection((host, 80)) as s:
    s.sendall(request)
    rawChunks = []
    while True:
      chunk = s.recv(1048576)
      if not chunk:
        break
      rawChunks.append(chunk)
    return b''.join(rawChunks)

def makeRequestString(command, t = None, gz = 1, market = 2, channel = 100012, version = client_version):
  if t is None:
    t = int(time.time() * 1000)

  secretkey = b'ade2688f1904e9fb8d2efdb61b5e398a'
  signature = hashlib.md5(str(t).encode('ASCII') + secretkey).hexdigest()
  return '{}&t={}&e={}&gz={}&market={}&channel={}&version={}'.format(command, t, signature, gz, market, channel, version)

def makeHTTPRequest(host, command, cookie, t = None):
  requestString = makeRequestString(command, t)
  return 'GET {} HTTP/1.1\r\nAccept-Encoding: identity\r\nCookie: {}\r\nUser-Agent: Dalvik/1.6.0 (Linux; U; Android 4.4.2; SM-G900F Build/KOT49H)\r\nHost: {}\r\nConnection: close\r\n\r\n'.format(requestString, cookie, host).encode('ASCII')

def makeHTTPRequestEx(method, host, command, cookie, contentType = None, content = None, t = None):
  fullQuery = makeRequestString(command, t)
  request = method + ' ' + fullQuery + ' HTTP/1.1\r\n'
  request += 'Accept-Encoding: identity\r\n'
  if cookie:
    request += 'Cookie: {}\r\n'.format(cookie)
  request += 'User-Agent: Dalvik/1.6.0 (Linux; U; Android 4.4.2; SM-G900F Build/KOT49H)\r\n'
  request += 'Host: {}\r\n'.format(host)
  request += 'Connection: close\r\n'
  if contentType:
    request += 'Content-Type: {}\r\n'.format(contentType)
  if content is not None:
    request += 'Content-Length: {}\r\n'.format(len(content))
  request += '\r\n'
  if content is not None:
    request += content
  return request.encode('ASCII')

assert(makeHTTPRequest('s5.jr.moefantasy.com',
    '/dock/getBuildBoatLog/',
    'hf_skey=1048056.1048056..1490440720.1.ade17b8423da87b4ffb4a03fd66f7966; path=/;QCLOUD=a',
    1490440738502) ==
  makeHTTPRequestEx('GET', 's5.jr.moefantasy.com', '/dock/getBuildBoatLog/',
    'hf_skey=1048056.1048056..1490440720.1.ade17b8423da87b4ffb4a03fd66f7966; path=/;QCLOUD=a',
    t = 1490440738502))

def dechunkHTTPResponse(response):
  originalResponse = response
  try:
    header, response = response.split(b'\r\n\r\n', 1)
    headerLines = header.split(b'\r\n')
    responseCode, codeMessage = re.fullmatch(br'^HTTP/1\.1 ([0-9]+) (.*)$', headerLines[0]).group(1, 2)
    responseCode = int(responseCode)
    if responseCode != 200:
      raise HTTPError(responseCode, codeMessage.decode('UTF-8'))
    data = bytes()
    while True:
      [size, tail] = response.split(b'\r\n', 1)
      size = int(size, 16)
      if size == 0:
        break
      else:
        data = data + tail[:size]
        response = tail[size + 2:]  # skip CRLF
    return data
  except Exception as e:
    logPath = 'error_response.{}.txt'.format(str(uuid.uuid1()))
    logFile = open(logPath, 'wb')
    logFile.write(originalResponse)
    logFile.close()
    raise

def decompressHTTPResponse(response):
  return zlib.decompress(dechunkHTTPResponse(response))

def decodeHTTPResponse(response):
  parsedResponse = json.loads(decompressHTTPResponse(response).decode('ASCII'), object_pairs_hook=collections.OrderedDict)
  if 'eid' in parsedResponse:
    raise ServerError(parsedResponse['eid'])
  if 'code' in parsedResponse and int(parsedResponse['code'] < 0):
    raise ServerError(parsedResponse['code'])
  return parsedResponse

def generateLoginRequestPass1(host, username, password):
  username = base64.b64encode(username.encode('UTF-8')).decode('ASCII')
  password = base64.b64encode(password.encode('UTF-8')).decode('ASCII')
  formData = 'username={}&pwd={}'.format(username, password)
  return makeHTTPRequestEx('POST', host, '/index/passportLogin/', None, 'application/x-www-form-urlencoded', formData)

def pickCookieFromResponse(response):
  headers = response.split(b'\r\n\r\n', 1)[0].split(b'\r\n')
  cookies = []
  uid = None
  for header in headers:
    m = re.match(br'^Set-Cookie: (([^;]+?)=([^;]+)).*$', header)
    if m:
      cookies.append(m.group(1))
      if m.group(2) == b'hf_skey':
        uid = m.group(3).split(b'.', 1)[0]
  if not uid:
    raise ValueError('UID is not found in cookies.')
  uid = int(uid)
  return (uid, b'; '.join(cookies).decode('ASCII'))

def issueCommand(gameServer, command, cookie, retryCount = 2):
  logger.info('Issuing command %s', command)
  request = makeHTTPRequestEx('GET', gameServer, command, cookie)
  for i in range(0, retryCount + 1):
    try:
      if i > 0:
        logger.warning('Retry %d/%d...', i, retryCount)
      response = sendRawHTTPRequest(gameServer, request)
      logger.info('Command finish')
      return decodeHTTPResponse(response)
    except HTTPError as e:
      logger.info('', exc_info = e)
      if e.code != 400:
        raise
    except socket.timeout:
      logger.info('', exc_info = True)

def commandSeries(gameServer, commands, cookie, interval):
  '''Returns: list<map>, a list of response data.'''
  isFirstOne = True
  responses = list()
  for command in commands:
    if interval and not isFirstOne:
      time.sleep(interval)
    responses.append(issueCommand(gameServer, command, cookie))
    isFirstOne = False
  return responses

def loginPass1(host, username, password):
  '''Returns uid and cookie string.'''
  request = generateLoginRequestPass1(host, username, password)
  response = sendRawHTTPRequest(host, request)
  try:
    return pickCookieFromResponse(response)
  except ValueError as e:
    raise LoginError('Cookie extraction failure') from e

def loginPass2(host, uid, cookie, version = client_version):
  command = '/index/login/{}?&client_version={}&phone_type=SM-G900F&phone_version=4.4.2&ratio=1600*900&service=unknown&udid=nopermission&source=android&affiliate=WIFI'.format(uid, version)
  data = issueCommand(host, command, cookie)
  if 'loginStatus' not in data or data['loginStatus'] != 1:
    raise LoginError('Logging into game server failed. Response: ' + str(data))

def login(loginServer, gameServer, username, password):
  uid, cookie = loginPass1(loginServer, username, password)
  loginPass2(gameServer, uid, cookie)
  return cookie

def register(loginServer, username, password, realName, realId):
  command = '/index/passportReg/{}/{}////?&realname={}&ID_card={}'.format(
      username, password, urllib.parse.quote_plus(realName, encoding = 'UTF-8'), realId)
  request = makeHTTPRequestEx('GET', loginServer, command, None)
  response = sendRawHTTPRequest(loginServer, request)
  try:
    return (True, pickCookieFromResponse(response))
  except:
    return (False, decodeHTTPResponse(response))

def createCharacter(gameServer, cookie, name, startCid):
  command = '/api/regRole/{}/{}/'.format(
      urllib.parse.quote_plus(name, encoding = 'UTF-8'), startCid)
  request = makeHTTPRequestEx('GET', gameServer, command, cookie)
  response = sendRawHTTPRequest(gameServer, request)
  data = decodeHTTPResponse(response)
  return data['status']

def simulateMainScreen(gameServer, cookie):
  return commandSeries(
      gameServer,
      [ '/bsea/getData/'
      , '/live/getUserInfo'
      , '/active/getUserData/'
      , '/pve/getUserData/'
      , '/campaign/getUserData/'
      ],
      cookie,
      1
  )

def fullLogin(loginServer, gameServer, username, password):
  '''Returns: (cookie, initGame, pveData, peventData, canBuy, bsea, userInfo, activeUserData, pveUserData, campaignUserData)'''
  cookie = login(loginServer, gameServer, username, password)
  initGame, pveData, peventData, canBuy = commandSeries(
      gameServer,
      [ '/api/initGame?&crazy=1'
      , '/pve/getPveData/'
      , '/pevent/getPveData/'
      , '/shop/canBuy/1/'
      ],
      cookie,
      1
  )
  time.sleep(1)
  bsea, userInfo, activeUserData, pveUserData, campaignUserData = simulateMainScreen(gameServer, cookie)
  return (cookie, initGame, pveData, peventData, canBuy, bsea, userInfo, activeUserData, pveUserData, campaignUserData)

def getExploreResult(gameServer, exploreId, cookie):
  data = issueCommand(gameServer, '/explore/getResult/{}/'.format(exploreId), cookie)
  if 'bigSuccess' not in data:
    raise ValueError('Expected field "bigSuccess" not found in response.')
  return data

def startExplore(gameServer, fleetId, exploreId, cookie):
  data = issueCommand(gameServer, '/explore/start/{}/{}/'.format(fleetId, exploreId), cookie)
  if 'exploreId' not in data:
    raise ValueError('Expected field "exploreId" not found in response.')
  if int(data['exploreId']) != exploreId:
    raise ValueError('Returned explore ID {} is not equal to the requested {}.'.format(
        int(data['exploreId']), exploreId))
  return data

def getCanonicalShipName(shipCid):
  return shipByCid[shipCid]['title']

def isHalfBroken(ship):
  hp = int(ship['battleProps']['hp'])
  maxHp = int(ship['battlePropsMax']['hp'])
  assert(maxHp > 0)
  return hp * 2 < maxHp

def isBroken(ship):
  hp = int(ship['battleProps']['hp'])
  maxHp = int(ship['battlePropsMax']['hp'])
  assert(maxHp > 0)
  return hp * 4 < maxHp
