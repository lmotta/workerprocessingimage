#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, datetime
from optparse import OptionParser

from osgeo import gdal
from gdalconst import GA_ReadOnly

from workerprocessingimage import WorkerProcessingImage

class WorkerLocalImage(WorkerProcessingImage):
  def __init__(self, idWorker):
    super(WorkerLocalImage, self).__init__( idWorker )
    
  def setImage(self, image):
    self._clear()
    self.nameImage = os.path.splitext(os.path.basename( image['name'] ) )[0]
    msg = None
    try:
      self.ds = gdal.Open( image['name'], GA_ReadOnly )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }
    
    self._setMetadata()
    return { 'isOk': True }

class WorkerPLScene(WorkerProcessingImage):
  PL_API_KEY = os.environ.get('PL_API_KEY')
  
  def __init__(self, idWorker):
    super(WorkerPLScene, self).__init__( idWorker )
    
  def setImage(self, image):
    if self.PL_API_KEY is None:
      msg = "API KEY for Planet Labs is not defined in host"
      return { 'isOk': False, 'msg': msg }

    self._clear()
    self.nameImage = image['name']
    opts = [
      ( 'VERSION', 'V0' ),
      ( 'API_KEY', self.PL_API_KEY ),
      ( 'SCENE', self.nameImage ),
      ( 'PRODUCT_TYPE', image['PRODUCT_TYPE'] )
    ]
    open_opts = map( lambda x: "%s=%s" % ( x[0], x[1] ), opts )
    msg = None
    try:
      self.ds = gdal.OpenEx( 'PLScenes:', gdal.OF_RASTER, open_options=open_opts )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }
    
    self._setMetadata()
    return { 'isOk': True }

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
  def printTime(title):
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print "%-75s %s" % ( title, t)

  def runAlgorithm(algorithm):
    printTime( "Running algorithm '%s'" % algorithm['name'] ) 
    vreturn = worker.run( algorithm )
    if not vreturn['isOk']:
      print "Error: %s" % vreturn['msg']
    else:
      printTime( "Create image '%s'" % vreturn['filename'] )

  set_worker = { 'local': setWorkerLocal, 'pl': setWorkerPLScene }
  ( worker, image ) = set_worker[ type_worker ]()

  printTime( "Setting Dataset '%s'(worker %s)" % ( image['name'], type_worker ) )
  vreturn = worker.setImage( image )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  algorithm = { 'name': 'mask', 'bands': None }  # Use last band
  runAlgorithm( algorithm )
  algorithm = { 'name': 'normalize_difference', 'bands': [ 1, 2 ] }
  runAlgorithm( algorithm )

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

