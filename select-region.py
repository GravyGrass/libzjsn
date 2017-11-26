#!/usr/bin/python3

from contextlib import closing
from datetime import datetime, timezone

import sqlite3
import sys

def strToEopch(t):
  return (datetime.strptime(t, '%Y-%m-%dT%H-%M%z') - datetime.fromtimestamp(0, timezone.utc)).total_seconds()

def selectRange(conn, baseName, tableName, schema, start, end):
  print('Processing {} to {}'.format(start, end))
  dstName = baseName
  conditions = list()
  params = list()
  if start:
    conditions.append('time >= ?')
    params.append(strToEopch(start))
    dstName = dstName + '.' + start
  else:
    dstName = dstName + '.0'
  if end:
    conditions.append('time < ?')
    params.append(strToEopch(end))
    dstName = dstName + '.' + end
  else:
    dstName = dstName + '.max'
  dstName += '.sqlite3'
  print('Generating {}'.format(dstName))
  with closing(sqlite3.connect(dstName)) as dst:
    dst.execute(schema)
  conn.execute('ATTACH DATABASE ? AS dst;', (dstName,))
  try:
    conn.execute('INSERT INTO dst.{} SELECT * FROM src.{} WHERE {};'.format(tableName, tableName, ' AND '.join(conditions)), tuple(params))
    count, first, last = conn.execute(
        'SELECT COUNT(*), datetime(MIN(time), "unixepoch", "localtime"), datetime(MAX(time), "unixepoch", "localtime") FROM dst.{}'.format(
            tableName)).fetchone()
    print('{} records from {} to {}'.format(count, first, last))
  finally:
    conn.execute('DETACH DATABASE dst;')

if len(sys.argv) != 5:
  sys.stderr.write('Usage: {} baseDb baseName tableName timePoints\n'.format(sys.argv[0]))
  exit(1)

baseDb = sys.argv[1]
baseName = sys.argv[2]
tableName = sys.argv[3]
timePoints = sys.argv[4]

conn = sqlite3.connect(':memory:')
conn.execute('ATTACH DATABASE ? AS src;', (baseDb,))
schema = conn.execute('SELECT sql FROM src.SQLITE_MASTER WHERE type = "table" AND tbl_name = ?', (tableName,)).fetchone()[0]
print(schema)
start = None
end = None
for line in open(timePoints, 'r', encoding = 'UTF-8'):
  line = line.strip()
  if line.startswith('#'):
    continue
  start = end
  end = line
  selectRange(conn, baseName, tableName, schema, start, end)
start = end
end = None
selectRange(conn, baseName, tableName, schema, start, end)
