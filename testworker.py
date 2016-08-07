#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, datetime
from optparse import OptionParser


from workerprocessingimage import WorkerLocalImage, WorkerPLScene

def setWorkerPLScene():
  WorkerPLScene.isKilled = False
  image = {
    'name': '20160421_110213_0c53',
    'PRODUCT_TYPE': "analytic"
  }
  idWorker = 1
  return ( WorkerPLScene( idWorker ), image )

def setWorkerLocal():
  WorkerLocalImage.isKilled = False
  image = {
    'name': '20160421_110213_0c53.tif'
  }
  idWorker = 1
  return ( WorkerLocalImage( idWorker ), image )

def run(type_worker):
  def printTime(title, t1=None):
    tn =datetime.datetime.now() 
    st = tn.strftime('%Y-%m-%d %H:%M:%S')
    stimes = st if t1 is None else  "%s %s" % ( st, str( tn - t1 ) )
    print "%-70s %s" % ( title, stimes )
    return tn

  def runAlgorithm(algorithm):
    t1 = printTime( "Running algorithm '%s'" % algorithm['name'] ) 
    vreturn = worker.run( algorithm )
    isOk, msg = True, None
    if not vreturn['isOk']:
      msg = vreturn['msg']
      isOk = False
    else:
      printTime( "Create image '%s'" % vreturn['filename'], t1 )
    
    return { 'isOk': isOk, 'msg': msg }

  set_worker = { 'local': setWorkerLocal, 'pl': setWorkerPLScene }
  ( worker, image ) = set_worker[ type_worker ]()

  printTime( "Setting Dataset '%s'(worker %s)" % ( image['name'], type_worker ) )
  vreturn = worker.setImage( image )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  algorithm = { 'name': 'mask', 'bands': None }  # Use last band
  vreturn = runAlgorithm( algorithm )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  algorithm = { 'name': 'normalize_difference', 'bands': [ 1, 2 ] }
  vreturn = runAlgorithm( algorithm )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']

def main():
  usage = "usage: %prog type_worker"
  parser = OptionParser(usage)

  # define options
  (opts, args) = parser.parse_args()

  if len(sys.argv) == 1:
    parser.print_help()
    return 1
  elif len(args) == 0:
    parser.print_help()
    return 1
  else:
    if not args[0] in ('local', 'pl'):
      print("Type of workers: 'local' or 'pl'.")
      return 1
    return run( args[0] )

if __name__ == "__main__":
    sys.exit( main() )

