#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Processing image framework
Description          : Processing image framework
Arguments            : Georeferencing Image local or Planet Labs

                       -------------------
begin                : 2016-08-11
copyright            : (C) 2016 by Luiz Motta
email                : motta dot luiz at gmail.com

 ***************************************************************************/
"""

import os, sys, argparse, datetime

from processingimage import CollectionAlgorithms, LocalImage, PLScene

def setPLScene(name_image):
  PLScene.isKilled = False
  image = {
    'name': name_image,
    'PRODUCT_TYPE': "analytic"
  }
  idWorker = 1
  return ( PLScene( idWorker ), image )

def setLocal(name_image):
  LocalImage.isKilled = False
  image = {
    'name': name_image
  }
  idWorker = 1
  return ( LocalImage( idWorker ), image )

def run(processing_type, name_image, subsetImage, name_algorithm, band_numbers):
  def printTime(title, t1=None):
    tn =datetime.datetime.now() 
    st = tn.strftime('%Y-%m-%d %H:%M:%S')
    stimes = st if t1 is None else  "%s %s" % ( st, str( tn - t1 ) )
    print "%-70s %s" % ( title, stimes )
    return tn

  def runAlgorithm(algorithm):
    t1 = printTime( "Running '%s'" % algorithm['name'] ) 
    vreturn = imageProcessing.run( algorithm )
    isOk, msg = True, None
    if not vreturn['isOk']:
      msg = vreturn['msg']
      isOk = False
    else:
      printTime( "Create '%s'" % vreturn['filename'], t1 )
    
    return { 'isOk': isOk, 'msg': msg }

  set_processing = { 'local': setLocal, 'pl': setPLScene }
  ( imageProcessing, image ) = set_processing[ processing_type ]( name_image )

  printTime( "Setting Dataset '%s'('%s')" % ( image['name'], processing_type ) )
  vreturn = imageProcessing.setImage( image, subsetImage )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  vreturn = runAlgorithm( { 'name': name_algorithm, 'bandNumbers': band_numbers } )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return

def main():
  processing_types = ( 'local', 'pl' )
  a_d = CollectionAlgorithms.descriptions
  d = "Image processing local or server(Planet Labs)."
  parser = argparse.ArgumentParser(description=d )
  d = "Type of process: %s" % " or ".join( processing_types )
  parser.add_argument('processing_type', metavar='processing_type', type=str, help=d )
  d = 'Name of scene(add extension for local)'
  parser.add_argument('namescene', metavar='name_scene', type=str, help=d )
  d = "Name of algorithm: %s" % ','.join( a_d.keys() )
  parser.add_argument('algorithm', metavar='algorithm', type=str, help=d )
  d = "Number of bands(separated by comma and no spaces). Ex.: 1,2"
  parser.add_argument('bands', metavar='bands', type=str, help=d )
  d = "Two coordinates, Upper Left and Bottom Right, separated by comma. Ex.: x_UL, y_UL, x_BR,y_BR"
  parser.add_argument('-s', metavar='subset', dest='subset', type=str, help=d )

  args = parser.parse_args()
  if not args.processing_type in processing_types:
    print "Type of processing '%s' not valid. Valids types: %s" % ( args.processing_type, " or ".join( processing_types ) )
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
    msg = "Total of bands '%d' is different of permited by algorithm '%s' '%d'." % ( t1, args.algorithm, t2 )
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
    subsetImage = { 'x_UL': coords[0], 'y_UL': coords[1], 'x_BR': coords[2], 'y_BR': coords[3] }
    if subsetImage['x_UL'] >= subsetImage['x_BR']:
      print "Coordinate x_UL '%d' is greater or equal than x_BR '%d'." % ( subsetImage['x_UL'], subsetImage['x_BR'] )
      return 1
    if subsetImage['y_UL'] >= subsetImage['y_BR']:
      print "Coordinate y_UL '%d' is greater or equal than y_BR '%d'." % ( subsetImage['y_UL'], subsetImage['y_BR'] )
      return 1

  return run( args.processing_type, args.namescene, subsetImage, args.algorithm, band_numbers )

if __name__ == "__main__":
    sys.exit( main() )
