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

import os, struct

from osgeo import gdal
from gdalconst import GA_ReadOnly
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')
gdal_sctruct_types = {
  gdal.GDT_Byte: 'B',
  gdal.GDT_UInt16: 'H',
  gdal.GDT_Int16: 'h',
  gdal.GDT_UInt32: 'I',
  gdal.GDT_Int32: 'i',
  gdal.GDT_Float32: 'f',
  gdal.GDT_Float64: 'd'
}

class WorkerValuesImage():
  def __init__(self, p ):
    band = p['ds'].GetRasterBand( p['bandNumbers'][0] )
    datatype = band.DataType
    
    # p['bandBlockSize'] ['x'],['y'], ['xy']
    
    # Read Band = nXOff, nYOff, nXSize, nYSize, nBufXSize, nBufYSize, eBufType
    # Read One Line
    self.dataRead = [ p['xoff'],  None, p['xsize'], 1, p['xsize'], 1, datatype ]
    self.fs = gdal_sctruct_types[ datatype ] * p['xsize']
    self.isSrcBand, self.src, self._getValues = False, None, None
    bandTotal = len( p['bandNumbers'] )
    if bandTotal > 1:
      self.src = p['ds']
      self.dataRead += [  p['bandNumbers'] ]
      self.fs *= bandTotal
      self._getValues = self._getValues2d
      band = None
    else:
      self.src = band
      self._getValues = self._getValues1d
      self.isSrcBand = True

  def __del__(self):
    if self.isSrcBand:
      self.src = None
    del self.fs
  
  def _getValues2d(self, data):
     l = list( struct.unpack( self.fs, data ) )
     n = self.dataRead[ 2 ] # xsize
     return [ l [ i : i + n ] for i in xrange( 0, len( l ), n ) ] # [ [band1], ..., [band2] ]

  def _getValues1d(self, data):
    return [ list( struct.unpack( self.fs, data ) ) ] # [ [band1] ]

  def getValues(self, row):
    self.dataRead[1] = row
    return self._getValues( self.src.ReadRaster( *self.dataRead ) ) 

class WorkerAlgorithms():
  algorithms_description = {
    'mask': {
      'description': "Calculate the mask, 255 for pixels > 0",
      'arguments': "Number of one band",
      'bandsRead': 1, 'bandsOut': 1,
      'datatype': gdal.GDT_Byte
    },
    'norm-diff': {
      'description': "Calculate normalize difference",
      'arguments': "Numbers of two bands",
      'bandsRead': 2, 'bandsOut': 1,
      'datatype': gdal.GDT_Float32
    }
  }

  def __init__(self):
    self.metadata, self.runAlgorithm = None, None
    self.algorithms = self.algorithms_description.copy()
    self.algorithms['mask'].update(      { 'func': self._algMask } )
    self.algorithms['norm-diff'].update( { 'func': self._algNormDiff } )

  def _algMask(self, values, x):
    band1 = values[ 0 ]
    return 255 if band1[ x ] > 0 else 0

  def _algNormDiff(self, values, x):
    band1 = values[ 0 ]
    band2 = values[ 1 ]
    vdiff = float( band1[ x ] - band2[ x ] )
    vsum  = float( band1[ x ] + band2[ x ] )
    return 0.0 if vsum == 0.0 else vdiff / vsum

  def setMetadata(self, metadata):
    self.metadata = metadata # xsize, xysize

  def setAlgorithm(self, name):
    self.runAlgorithm = self.algorithms[ name ]['func']

  def run(self, values, x):
    return self.runAlgorithm( values, x )

class WorkerProcessingImage(object):
  isKilled = False
  driverMem = gdal.GetDriverByName('MEM')
  driverTif = gdal.GetDriverByName('GTiff')

  def __init__(self, idWorker):
    super(WorkerProcessingImage, self).__init__()
    self.idWorker = idWorker
    self.wAlgorithm = WorkerAlgorithms()
    self.nameImage, self.ds, self.metadata = None, None, None
    self.bandNumbers, self.bandBlockSize = None, None
  
  def __del__(self):
    self._clear()

  def _clear(self):
    self.ds = None
    if not self.metadata is None:
      self.metadata.clear()

  def _processBandOut(self, outDS):
    linesRead = 1
    p = {
      'ds': self.ds, 'bandNumbers': self.bandNumbers, 'bandBlockSize': self.bandBlockSize,
      'xsize':  self.metadata['xsize'], 'xoff': self.metadata['xoff'],
      'ysize':  self.metadata['ysize'], 'yoff': self.metadata['yoff'],
      'xysize': self.metadata['xysize']
    }
    wvi = WorkerValuesImage( p )
    outBand = outDS.GetRasterBand(1)
    outBand.SetNoDataValue( 0)
    
    fs = gdal_sctruct_types[ outBand.DataType ] * p['xsize']
    outValues = p['xsize'] * [ None ]
    xx = xrange( p['xsize'] )
    for y in xrange( p['ysize'] ):
      imgValues = wvi.getValues( y ) # [ [ band 1 ], ...,[ band N ] ]
      if self.isKilled:
        del imgValues[:]
        break
      for x in xx:
        outValues[ x ] = self.wAlgorithm.run( imgValues, x )
      del imgValues[:]
      data = struct.pack( fs, *outValues )
      outBand.WriteRaster( 0, y, outDS.RasterXSize, 1, data )
      del data
    del outValues[:]
    del fs
    outBand.FlushCache()
    outBand = None
    del wvi

  def _endSetImage(self, subset):
    def setMetadata():
      xoff, xsize, yoff, ysize = 0, self.ds.RasterXSize, 0, self.ds.RasterYSize
      transform = self.ds.GetGeoTransform()
      haveSubset = False
      if not subset is None:
        xoff,  yoff  = subset['x_UL'], subset['y_UL']
        xsize, ysize = subset['x_BR'] - subset['x_UL'], subset['y_BR'] - subset['y_UL']
        lt = list( transform )
        lt[0] += xoff * transform[1]
        lt[3] += yoff * transform[5]
        transform = tuple( lt )
        haveSubset = True
      self.metadata = {
          'transform': transform,
          'srs': self.ds.GetProjection(),
          'xsize': xsize, 'xoff': xoff, 'ysize': ysize, 'yoff': yoff,
          'xysize': xsize * ysize, 'subset': haveSubset,
          'totalbands': self.ds.RasterCount
      }
      self.wAlgorithm.setMetadata( { 'xsize': xsize, 'ysize': ysize } )

    def checkSubset():
      def checkOut(size, tcoord, title):
        for c in ( 'UL', 'BR' ):
          s = subset[ "%s_%s" % ( tcoord, c )]
          if s > size:
            data = ( tcoord, c, s, title, size  )
            msg = "Coordinate %s_%s '%d' is greater than number of %s '%d'" % data
            return { 'isOk': False, 'msg': msg }
        return { 'isOk': True }

      vreturn = checkOut( self.ds.RasterXSize, 'x', "columns" )
      if not vreturn['isOk']:
        return vreturn
      return checkOut( self.ds.RasterXSize, 'y', "lines")
    
    if not subset is None:
      vreturn = checkSubset()
      if not vreturn['isOk']:
        return vreturn

    setMetadata()
    return { 'isOk': True }
  
  #def setImage(self, image, subset):
    # self._clear()
    #...
    # Set: self.nameImage, self.ds 
    # ...
    # return self._endSetImage(subset) 

  def run(self, algorithm):
    def getNameOut():
      subset = "_subset" if self.metadata ['subset'] else ""
      bands = "-".join( map( lambda i: "B%d" % i, self.bandNumbers ) )
      d = ( self.nameImage, subset, algorithm['name'], bands, self.idWorker )
      return "%s%s_%s_%s_work%d.tif" % d

    def createDSOut():
      def removeOut():
        if os.path.exists( filenameOut ):
          os.remove( filenameOut )
        aux = "%s.aux.xml" % filenameOut
        if os.path.exists( aux ):
          os.remove( aux )

      dataAlg = WorkerAlgorithms.algorithms_description[ algorithm['name'] ]
      removeOut()
      d = (
        filenameOut, self.metadata['xsize'], self.metadata['ysize'],
        dataAlg['bandsOut'], dataAlg['datatype']
      )
      ds = None
      try:
        ds = self.driverTif.Create( *d )
      except RuntimeError:
        return None
      ds.SetProjection( self.metadata['srs'] )
      ds.SetGeoTransform( self.metadata['transform'] )
      return ds

    def checkBandNumbersAlgorithm():
      for i in xrange( len( algorithm['bandNumbers'] ) ):
        bn = algorithm['bandNumbers'][ i ]
        if bn > self.metadata['totalbands']:
          msg = "Band '%d' is greater than total of bands '%d'" % ( bn, self.metadata['totalbands'] )
          return { 'isOk': False, 'msg': msg }
      return { 'isOk': True }

    def checkBandBlockSizes(bands):
      bandBlockSizes = map( lambda b: b.GetBlockSize(), bands )
      sizeX, sizeY = bandBlockSizes[ 0 ][ 0 ], bandBlockSizes[ 0 ][ 1 ]
      for i in xrange( 1, len( bandBlockSizes ) ):
        if sizeX != bandBlockSizes[ i ][ 0 ] or sizeY != bandBlockSizes[ i ][ 1 ]:
          msg = ",".join( map( lambda b: str(b), self.bandNumbers ) )
          msg = "Bands '%s' of image '%s' have different block sizes" % ( msg, self.nameImage )
          return { 'isOk': False, 'msg': msg }
      return { 'isOk': True }

    def checkBandDatatypes(bands):
      datatypes = map( lambda b: b.DataType, bands )
      datatype = datatypes[0]
      for i in xrange( 1, len( datatypes) ):
        if datatype != datatypes[ i ]:
          msg = ",".join( map( lambda b: str(b), self.bandNumbers ) )
          msg = "Bands '%s' of image '%s' have different data types" % ( msg, self.nameImage )
          return { 'isOk': False, 'msg': msg }
      return { 'isOk': True }

    vreturn = checkBandNumbersAlgorithm()
    if not vreturn['isOk']:
      return vreturn
    self.bandNumbers = algorithm['bandNumbers']

    bands = map( lambda b: self.ds.GetRasterBand( b ), self.bandNumbers )
    self.bandBlockSizes = bands[0].GetBlockSize()
    self.datatype = bands[0].DataType
    bandTotal = len( bands )
    if bandTotal > 1: 
      vreturn = checkBandBlockSizes( bands )
      if not vreturn['isOk']:
        del bands[:]
        return vreturn
      vreturn = checkBandDatatypes( bands )
      if not vreturn['isOk']:
        del bands[:]
        return vreturn
    del bands[:]

    filenameOut = getNameOut()
    ds = createDSOut()
    if ds is None:
      msg = "Creating output image from '%s'" % self.nameImage
      return { 'isOk': False, 'msg': msg }
    
    self.wAlgorithm.setAlgorithm( algorithm['name'] )
    self._processBandOut( ds )

    ds = None
    return { 'isOk': True, 'filename': filenameOut }

class WorkerLocalImage(WorkerProcessingImage):
  def __init__(self, idWorker):
    super(WorkerLocalImage, self).__init__( idWorker )
    
  def setImage(self, image, subset):
    self._clear()
    self.nameImage = os.path.splitext(os.path.basename( image['name'] ) )[0]
    msg = None
    try:
      self.ds = gdal.Open( image['name'], GA_ReadOnly )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }

    return self._endSetImage( subset )

class WorkerPLScene(WorkerProcessingImage):
  PL_API_KEY = os.environ.get('PL_API_KEY')
  
  def __init__(self, idWorker):
    super(WorkerPLScene, self).__init__( idWorker )
    
  def setImage(self, image, subset):
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

    return self._endSetImage( subset )
