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

from processingimage import RegionImage, CollectionAlgorithms, LocalImage, PLScene

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

def run(processing_type, name_image, name_algorithm, band_numbers, wkt):
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
  vreturn = imageProcessing.setImage( image, wkt )
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
  d = "WKT(between double quotes) for region. Use EPSG 4326 for SRS" 
  parser.add_argument('-w', metavar='WKT_Region', dest='wkt4326', type=str, help=d)

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
      
  if not args.wkt4326 is None and not RegionImage.isValidGeom( args.wkt4326 ): 
    print "The WKT '%s' not valid." % args.wkt4326
    return 1

  return run( args.processing_type, args.namescene, args.algorithm, band_numbers, args.wkt4326 )

if __name__ == "__main__":
    sys.exit( main() )
