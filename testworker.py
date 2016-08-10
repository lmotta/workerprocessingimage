#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, argparse, datetime

from workerprocessingimage import WorkerAlgorithms, WorkerLocalImage, WorkerPLScene

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

  printTime( "Setting Dataset '%s'('%s')" % ( image['name'], type_worker ) )
  vreturn = worker.setImage( image, subsetImage )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  vreturn = runAlgorithm( { 'name': name_algorithm, 'bandNumbers': band_numbers } )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return

def main():
  type_process = ( 'local', 'pl' )
  a_d = WorkerAlgorithms.algorithms_description
  d = "Image processing local or server(Planet Labs)."
  parser = argparse.ArgumentParser(description=d )
  d = "Type of process: %s" % " or ".join( type_process )
  parser.add_argument('type_process', metavar='type_process', type=str, help=d )
  d = 'Name of scene(add extension for local)'
  parser.add_argument('namescene', metavar='name_scene', type=str, help=d )
  d = "Name of algorithm: %s" % ','.join( a_d.keys() )
  parser.add_argument('algorithm', metavar='algorithm', type=str, help=d )
  d = "Number of bands(separated by comma and no spaces). Ex.: 1,2,3"
  parser.add_argument('bands', metavar='bands', type=str, help=d )
  d = "Two coordinates of image(separated by comma). Ex.: x1,y1,x2,y2"
  parser.add_argument('-s', metavar='subset', dest='subset', type=str, help=d )

  args = parser.parse_args()
  if not args.type_process in type_process:
    print "Type of processing '%s' not valid. Valids types: %s" % ( args.type_process, " or ".join( type_process ) )
    return 1
  if not args.algorithm in a_d.keys():
    print "Type of algorithm '%s' not valid." % args.algorithm 
    descs = []
    for k in a_d.keys():
      desc = "'%s': %s - %s" % ( k, a_d[k]['description'], a_d[k]['arguments'] ) 
      descs.append( desc )
    print  'Valids types:\n'.join(descs)
    return 1
  values = args.bands.split(',')
  for i in xrange( len( values ) ):
    if not values[ i ].isdigit():
      print "Band '%s' is not a number." % values[ i ]
      return 1
  band_numbers = map( lambda s: int(s), values )
  
  t1 = len( band_numbers )
  t2 = a_d[args.algorithm]['bandsRead']
  if not t1 == t2:
    msg = "Total of bands '%d' is greater then permited by algorithm '%s' '%d'." % ( t1, args.algorithm, t2 )
    print msg
    return 1
      
  subsetImage = None
  if not args.subset is None:
    values = args.subset.split(',')
    for i in xrange( len( values ) ):
      if not values[ i ].isdigit():
        print "Coordinate '%s' is not a number." % values[ i ]
        return 1
    coords = map( lambda s: int(s), values )
    if not len( coords ) == 4:
      print "Need four coordinates for subset '-s', receive '%d' coordinates." % len( coords )
      return 1
    subsetImage = { 'x1': coords[0], 'y1': coords[1], 'x2': coords[2], 'y2': coords[3] }
    if subsetImage['x1'] > subsetImage['x2']:
      print "Coordinate x1 '%d' is greater then x2 '%d'." % ( subsetImage['x1'], subsetImage['x2'] )
      return 1
    if subsetImage['y1'] > subsetImage['y2']:
      print "Coordinate y1 '%d' is greater then y2 '%d'." % ( subsetImage['y1'], subsetImage['y2'] )
      return 1
    if subsetImage['x1'] == subsetImage['x2']:
      print "Coordinate x1 '%d' is equal to x2 '%d'." % ( subsetImage['x1'], subsetImage['x2'] )
      return 1
    if subsetImage['y1'] == subsetImage['y2']:
      print "Coordinate y1 '%d' is equal to y2 '%d'." % ( subsetImage['y1'], subsetImage['y2'] )
      return 1

  return run( args.type_process, args.namescene, subsetImage, args.algorithm, band_numbers )

if __name__ == "__main__":
    sys.exit( main() )

# testworker.py pl 20160421_110213_0c53
# testworker.py local 20160421_110213_0c53.tif
