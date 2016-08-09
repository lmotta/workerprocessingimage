#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, argparse, datetime

from workerprocessingimage import WorkerLocalImage, WorkerPLScene

def setWorkerPLScene(name_image):
  WorkerPLScene.isKilled = False
  image = {
    'name': name_image,
    'PRODUCT_TYPE': "analytic"
  }
  idWorker = 1
  return ( WorkerPLScene( idWorker ), image )

def setWorkerLocal(name_image):
  WorkerLocalImage.isKilled = False
  image = {
    'name': name_image
  }
  idWorker = 1
  return ( WorkerLocalImage( idWorker ), image )

def run(type_worker, name_image, subsetImage, name_algorithm, band_numbers):
  def printTime(title, t1=None):
    tn =datetime.datetime.now() 
    st = tn.strftime('%Y-%m-%d %H:%M:%S')
    stimes = st if t1 is None else  "%s %s" % ( st, str( tn - t1 ) )
    print "%-70s %s" % ( title, stimes )
    return tn

  def runAlgorithm(algorithm):
    t1 = printTime( "Running '%s'" % algorithm['name'] ) 
    vreturn = worker.run( algorithm )
    isOk, msg = True, None
    if not vreturn['isOk']:
      msg = vreturn['msg']
      isOk = False
    else:
      printTime( "Create '%s'" % vreturn['filename'], t1 )
    
    return { 'isOk': isOk, 'msg': msg }

  set_worker = { 'local': setWorkerLocal, 'pl': setWorkerPLScene }
  ( worker, image ) = set_worker[ type_worker ]( name_image )

  printTime( "Setting Dataset '%s'(worker %s)" % ( image['name'], type_worker ) )
  vreturn = worker.setImage( image, subsetImage )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  algorithm = { 'name': name_algorithm, 'bandNumbers': band_numbers }
  vreturn = runAlgorithm( algorithm )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return

def main():
  # https://docs.python.org/2/library/argparse.html#module-argparse
  a_d = WorkerLocalImage.algorithms_description
  descs = []
  for k in a_d.keys():
    desc = "%s: %s - Arguments: %s" % ( k, a_d[ k ]['description'], a_d[ k ]['arguments'] )
    descs.append( desc)
  description = "Image processing local or server(Planet labs)\n%s" % "\n".join( descs )
  parser = argparse.ArgumentParser(description=description)
  parser.add_argument('type_process', metavar='type_process', type=str, help="Type of process('local' or 'pl')" )
  parser.add_argument('namescene', metavar='name_scene', type=str, help='Name of scene(add extension for local)' )
  parser.add_argument('algorithm', metavar='algorithm', type=str, help="Name of algorithm(%s)" % ''.join( a_d.keys() ) )
  
  
  args = parser.parse_args()
  if not args.type_process in ( 'local', 'pl'):
    print "Type of processing '%s' not valid." % args.type_process 
    print parser.description
    return 1
  if not args.algorithm in a_d.keys():
    print "Type of algorithm '%s' not valid." % args.type_process 
    print parser.description
    return 1

  #subsetImage = None # { }
  subsetImage = { 'x1': 1862, 'y1': 1840, 'x2': 2048, 'y2': 2024 }
  v_band_numbers = {
    'mask': None, # Get last
    'norm-diff': [ 1, 2 ] 
  }
  band_numbers = v_band_numbers[ args.algorithm ]
  return run( args.type_process, args.namescene, subsetImage, args.algorithm, band_numbers )

if __name__ == "__main__":
    sys.exit( main() )

# testworker.py pl 20160421_110213_0c53
# testworker.py local 20160421_110213_0c53.tif
