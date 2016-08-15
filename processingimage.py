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

import os, struct, math

from osgeo import gdal, ogr, osr
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

class RegionImage():
  def __init__(self, ds):
    self.ds = ds
    self.ulImage, self.resImage = None, None
  
  def _getGeom(self):
    def getWktBBox( UL, BR):
      coords = [ ( UL['x'], UL['y'] ), ( BR['x'], UL['y'] ), ( BR['x'], BR['y'] ), ( UL['x'], BR['y'] ), ( UL['x'], UL['y'] ) ]
      coords = map( lambda c: "%f %f" % ( c[0], c[1] ), coords)
      return "POLYGON (( %s ))" % ','.join( coords )

    transform = self.ds.GetGeoTransform()
    self.ulImage  = { 'x': transform[0], 'y': transform[3] }
    self.resImage = { 'x': transform[1], 'y': transform[5] }
    xsize, ysize = self.ds.RasterXSize, self.ds.RasterYSize
    BR = { 'x': self.ulImage['x'] + transform[1] * xsize, 'y': self.ulImage['y'] + transform[5] * ysize }
    wktGeom = getWktBBox( self.ulImage, BR )
    
    wktSRS = self.ds.GetProjectionRef()
    if wktSRS == '':
      return { 'isOk': False, 'msg': "Image not have Spatial Reference" }

    sr = osr.SpatialReference()
    sr.ImportFromWkt( wktSRS )
    geom = ogr.CreateGeometryFromWkt( wktGeom )
    geom.AssignSpatialReference( sr )
    
    return { 'isOk': True, 'geom': geom }

  def getSubset(self, wkt4326):
    def getGeomWkt4326():
      geom = ogr.CreateGeometryFromWkt( wkt4326 )
      sr = osr.SpatialReference()
      sr.ImportFromEPSG( 4326 )
      geom.AssignSpatialReference( sr )
      geom.TransformTo( geomImg.GetSpatialReference() )
      
      return geom

    def getPixelCoordinate(x, y):
      self.ulImage, self.resImage
      xCell = ( x - self.ulImage['x'] ) / self.resImage['x'] 
      yCell = ( y - self.ulImage['y'] ) / self.resImage['y']
      
      return { 'x': int( math.ceil( xCell ) ), 'y': int( math.ceil( yCell ) ) }

    vreturn = self._getGeom()
    if not vreturn['isOk']:
      print msg
      return
    geomImg = vreturn['geom']
    geom = getGeomWkt4326()
    msg = "Wkt Geom not intersect with image:\nWkt '%s'\nImage = '%s'" % ( wkt4326, self.ds.GetDescription() )
    if not geomImg.Intersect( geom ):
      geomImg.Destroy()
      geom.Destroy()
      return { 'isOk': False, 'msg': msg }
    geomRegion = geomImg.Intersection( geom )
    geomImg.Destroy()
    geom.Destroy()
    if not geomRegion.GetDimension() == 2:
      geomRegion.Destroy()
      return { 'isOk': False, 'msg': msg }

    ( minX, maxX, minY, maxY )= geomRegion.GetEnvelope()
    geomRegion.Destroy()
    
    ul = getPixelCoordinate( minX, maxY )
    br = getPixelCoordinate( maxX, minY )
    subset = {
      'x_UL': ul['x'], 'y_UL': ul['y'],
      'x_BR': br['x'], 'y_BR': br['y'],
    }

    return { 'isOk': True, 'subset': subset }

  @staticmethod
  def isValidGeom(wkt4326):
    try:
      geom = ogr.CreateGeometryFromWkt( wkt4326 )
    except RuntimeError:
      pass # The exception not enter here, but, not show GDAL message!
    if geom is None:
      return False
    geom.Destroy()
    return True

class ImageLineValues():
  def __init__(self, p ):
    band = p['ds'].GetRasterBand( p['bandNumbers'][0] ) # See self.src
    datatype = band.DataType
    self.dataRead = [ p['xoff'],  None, p['xsize'], 1, p['xsize'], 1, datatype ]
    self.yoff = p['yoff'] # Subset
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
     n = self.dataRead[ 2 ] #  self.dataRead[ 2 ] = xsize
     return [ l [ i : i + n ] for i in xrange( 0, len( l ), n ) ] # [ [band1], ..., [band2] ]

  def _getValues1d(self, data):
    return [ list( struct.unpack( self.fs, data ) ) ] # [ [band1] ]

  def getValues(self, row):
    self.dataRead[1] = self.yoff + row
    return self._getValues( self.src.ReadRaster( *self.dataRead ) ) 

class CollectionAlgorithms():
  descriptions = {
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
    self.runAlgorithm = None
    self.algorithms = self.descriptions.copy()
    algs = (
      ( 'mask', self._algMask ),
      ( 'norm-diff', self._algNormDiff )
    )
    for item in algs:
      self.algorithms[ item[0] ].update( { 'func': item[1] } )

  def _algMask(self, values, x):
    band1 = values[ 0 ]
    return 255 if band1[ x ] > 0 else 0

  def _algNormDiff(self, values, x):
    band1 = values[ 0 ]
    band2 = values[ 1 ]
    vdiff = float( band1[ x ] - band2[ x ] )
    vsum  = float( band1[ x ] + band2[ x ] )
    return 0.0 if vsum == 0.0 else vdiff / vsum

  def setAlgorithm(self, name):
    self.runAlgorithm = self.algorithms[ name ]['func']

  def run(self, values, x):
    return self.runAlgorithm( values, x )

class ProcessingImage(object):
  isKilled = False
  driverMem = gdal.GetDriverByName('MEM')
  driverTif = gdal.GetDriverByName('GTiff')

  def __init__(self, idWorker):
    super(ProcessingImage, self).__init__()
    self.idWorker = idWorker
    self.wAlgorithm = CollectionAlgorithms()
    self.nameImage, self.ds, self.metadata = None, None, None
    self.bandNumbers = None
  
  def __del__(self):
    self._clear()

  def _clear(self):
    self.ds = None
    if not self.metadata is None:
      self.metadata.clear()

  def _processBandOut(self, outDS):
    p = { 'ds': self.ds, 'bandNumbers': self.bandNumbers }
    for key in ( 'xoff', 'yoff', 'xsize' ):
      p[ key ] = self.metadata[ key ]  
    wvi = ImageLineValues( p )
    outBand = outDS.GetRasterBand(1)
    fs = gdal_sctruct_types[ outBand.DataType ] * p['xsize']
    outValues = p['xsize'] * [ None ]
    xx = xrange( p['xsize'] )
    for y in xrange( self.metadata['ysize'] ):
      imgValues = wvi.getValues( y ) # [ [ band 1 ], ...,[ band N ] ], Use xoff and yoff for Subset
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
    outBand.SetNoDataValue( 0 )
    outBand.FlushCache()
    outBand = None
    del wvi

  def _endSetImage(self, wkt):
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
          'xoff': xoff, 'yoff': yoff, 'xsize': xsize,'ysize': ysize,
          'subset': haveSubset, 'totalbands': self.ds.RasterCount
      }


    if not wkt is None:
      ri = RegionImage( self.ds )
      vreturn = ri.getSubset( wkt )
      if not vreturn['isOk']:
        return vreturn
      subset = vreturn['subset']
    else:
      subset = None

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

      dataAlg = CollectionAlgorithms.descriptions[ algorithm['name'] ]
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

class LocalImage(ProcessingImage):
  def __init__(self, idWorker):
    super(LocalImage, self).__init__( idWorker )
    
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

class PLScene(ProcessingImage):
  PL_API_KEY = os.environ.get('PL_API_KEY')
  
  def __init__(self, idWorker):
    super(PLScene, self).__init__( idWorker )
    
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
