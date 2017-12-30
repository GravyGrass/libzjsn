# encoding: UTF-8

import libzjsn

libzjsn.loadConfig()

def testServerErrorKnown():
  error = libzjsn.ServerError({'eid': -9999})
  assert(error.errorCode == -9999)
  assert(error.message == "服务器正在维护")

def testServerErrorUnknown():
  error = libzjsn.ServerError({'eid': -7654})
  assert(error.errorCode == -7654)
  assert(error.message == "Unknown error -7654")

cases = [testServerErrorKnown, testServerErrorUnknown]

for case in cases:
  case()
