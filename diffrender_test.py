__author__ = 'pol'

import matplotlib
matplotlib.use('Qt4Agg')
import scene_io_utils
import mathutils
from math import radians
import timeit
import time
import opendr
import chumpy as ch
import geometry
import image_processing
import numpy as np
import cv2
import glfw
import generative_models
import recognition_models
import matplotlib.pyplot as plt
from opendr_utils import *
from utils import *
import OpenGL.GL as GL
import light_probes
from OpenGL import contextdata
import theano
# theano.sandbox.cuda.use('cpu')
import lasagne
import lasagne_nn

plt.ion()

#########################################
# Initialization starts here
#########################################

#Main script options:

glModes = ['glfw','mesa']
glMode = glModes[0]

width, height = (150, 150)
win = -1

if glMode == 'glfw':
    #Initialize base GLFW context for the Demo and to share context among all renderers.
    glfw.init()
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    # glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL.GL_TRUE)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.DEPTH_BITS,32)
    glfw.window_hint(glfw.VISIBLE, GL.GL_FALSE)
    win = glfw.create_window(width, height, "Demo",  None, None)
    glfw.make_context_current(win)

angle = 60 * 180 / np.pi
clip_start = 0.05
clip_end = 10
frustum = {'near': clip_start, 'far': clip_end, 'width': width, 'height': height}
camDistance = 0.4

teapots = [line.strip() for line in open('teapots.txt')]

# renderTeapotsList = np.arange(len(teapots))
renderTeapotsList = np.arange(len(teapots))[0:1]

targetModels = []

v_teapots, f_list_teapots, vc_teapots, vn_teapots, uv_teapots, haveTextures_list_teapots, textures_list_teapots, vflat, varray, center_teapots = scene_io_utils.loadTeapotsOpenDRData(renderTeapotsList, False, False, targetModels)

azimuth = np.pi
chCosAz = ch.Ch([np.cos(azimuth)])
chSinAz = ch.Ch([np.sin(azimuth)])

chAz = 2*ch.arctan(chSinAz/(ch.sqrt(chCosAz**2 + chSinAz**2) + chCosAz))
chAz = ch.Ch([0])
chObjAz = ch.Ch([0])
chAzRel = chAz - chObjAz

elevation = 0
chLogCosEl = ch.Ch(np.log(np.cos(elevation)))
chLogSinEl = ch.Ch(np.log(np.sin(elevation)))
chEl = 2*ch.arctan(ch.exp(chLogSinEl)/(ch.sqrt(ch.exp(chLogCosEl)**2 + ch.exp(chLogSinEl)**2) + ch.exp(chLogCosEl)))
chEl =  ch.Ch([0.95993109])
chDist = ch.Ch([camDistance])

chLightSHCoeffs = ch.Ch(np.array([2, 0.25, 0.25, 0.12,-0.17,0.36,0.1,0.,0.]))

clampedCosCoeffs = clampedCosineCoefficients()
chComponent = chLightSHCoeffs * clampedCosCoeffs

chPointLightIntensity = ch.Ch([1])

chLightAz = ch.Ch([0.0])
chLightEl = ch.Ch([np.pi/2])
chLightDist = ch.Ch([0.5])

light_color = ch.ones(3)*chPointLightIntensity

chVColors = ch.Ch([0.4,0.4,0.4])

chDisplacement = ch.Ch([0.0, 0.0,0.0])
chScale = ch.Ch([1.0,1.0,1.0])

# vcch[0] = np.ones_like(vcflat[0])*chVColorsGT.reshape([1,3])
renderer_teapots = []

for teapot_i in range(len(renderTeapotsList)):
    vmod = v_teapots[teapot_i]
    fmod_list = f_list_teapots[teapot_i]
    vcmod = vc_teapots[teapot_i]
    vnmod = vn_teapots[teapot_i]
    uvmod = uv_teapots[teapot_i]
    haveTexturesmod_list = haveTextures_list_teapots[teapot_i]
    texturesmod_list = textures_list_teapots[teapot_i]
    centermod = center_teapots[teapot_i]
    renderer = createRendererTarget(glMode, chAz, chObjAz, chEl, chDist, centermod, vmod, vcmod, fmod_list, vnmod, light_color, chComponent, chVColors, 0, chDisplacement, chScale, width,height, uvmod, haveTexturesmod_list, texturesmod_list, frustum, win )
    renderer.r
    renderer_teapots = renderer_teapots + [renderer]

currentTeapotModel = 0

center = center_teapots[currentTeapotModel]

#########################################
# Initialization ends here
#########################################

#########################################
# Generative model set up
#########################################

rendererGT = ch.Ch(renderer.r.copy())
numPixels = width*height

E_raw = renderer - rendererGT
SE_raw = ch.sum(E_raw*E_raw, axis=2)

SSqE_raw = ch.SumOfSquares(E_raw)/numPixels

initialPixelStdev = 0.01
reduceVariance = False
# finalPixelStdev = 0.05
stds = ch.Ch([initialPixelStdev])
variances = stds ** 2
globalPrior = ch.Ch([0.9])

negLikModel = -ch.sum(generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances))/numPixels
negLikModelRobust = -ch.sum(generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances))/numPixels
pixelLikelihoodCh = generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances)
pixelLikelihoodRobustCh = generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances)
# negLikModel = -generative_models.modelLogLikelihoodCh(rendererGT, renderer, np.array([]), 'FULL', variances)/numPixels
# negLikModelRobust = -generative_models.modelLogLikelihoodRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances)/numPixels
# pixelLikelihoodCh = generative_models.logPixelLikelihoodCh(rendererGT, renderer, np.array([]), 'FULL', variances)
# pixelLikelihoodRobustCh = ch.log(generative_models.pixelLikelihoodRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances))

post = generative_models.layerPosteriorsRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances)[0]



# models = [negLikModel, negLikModelRobust, hogError]
models = [negLikModel, negLikModelRobust, negLikModelRobust]
# pixelModels = [pixelLikelihoodCh, pixelLikelihoodRobustCh, hogCellErrors]
pixelModels = [pixelLikelihoodCh, pixelLikelihoodRobustCh, pixelLikelihoodRobustCh]
modelsDescr = ["Gaussian Model", "Outlier model", "HOG"]

model = 0
pixelErrorFun = pixelModels[model]
errorFun = models[model]
iterat = 0

t = time.time()

def cb(_):
    global t
    global samplingMode
    elapsed_time = time.time() - t
    print("Ended interation in  " + str(elapsed_time))

    # if samplingMode:
    #     analyzeAz(resultDir + 'az_samples/test' + str(test_i) +'/azNum' + str(sampleAzNum) + '_it' + str(iterat)  , rendererGT, renderer, chEl.r, chVColors.r, chLightSHCoeffs.r, azsPredictions[test_i], sampleStds=stds.r)
    # else:
    #     analyzeAz(resultDir + 'az_samples/test' + str(test_i) +'/min_azNum' + str(sampleAzNum) +  '_it' + str(iterat)  , rendererGT, renderer, chEl.r, chVColors.r, chLightSHCoeffs.r, azsPredictions[test_i], sampleStds=stds.r)

    global pixelErrorFun
    global errorFun
    global iterat
    iterat = iterat + 1
    print("Callback! " + str(iterat))
    print("Sq Error: " + str(errorFun.r))
    global imagegt
    global renderer
    global gradAz
    global gradEl
    global performance
    global azimuths
    global elevations

    t = time.time()

#########################################
# Generative model setup ends here.
#########################################

#########################################
# Test code starts here:
#########################################

seed = 1
np.random.seed(seed)

# testPrefix = 'train4_occlusion_opt_train4occlusion10k_100s_dropoutsamples_std01_nnsampling_minSH'
testPrefix = 'train4_occlusion_2samplestest'
# testPrefix = 'train4_occlusion_opt_train4occlusion10k_10s_std01_bad'

parameterRecognitionModels = set(['randForestAzs', 'randForestElevs', 'randForestVColors', 'linearRegressionVColors', 'neuralNetModelSHLight', ])
parameterRecognitionModels = set(['randForestAzs', 'randForestElevs', 'randForestVColors', 'linearRegressionVColors', 'linRegModelSHZernike' ])
parameterRecognitionModels = set(['randForestAzs', 'randForestElevs','linearRegressionVColors','neuralNetModelSHLight' ])
parameterRecognitionModels = set(['neuralNetPose', 'linearRegressionVColors','constantSHLight' ])
parameterRecognitionModels = set(['neuralNetPose', 'neuralNetApperanceAndLight', 'neuralNetVColors' ])
parameterRecognitionModels = set(['neuralNetPose', 'neuralNetModelSHLight', 'neuralNetVColors' ])
# parameterRecognitionModels = set(['neuralNetPose', 'neuralNetApperanceAndLight'])

# parameterRecognitionModels = set(['randForestAzs', 'randForestElevs','randForestVColors','randomForestSHZernike' ])

gtPrefix = 'train4_occlusion'
experimentPrefix = 'train4_occlusion'
trainPrefixPose = 'train4_occlusion_10k'
trainPrefixVColor = 'train4_occlusion_10k'
trainPrefixLightCoeffs = 'train4_occlusion_10k'
trainModelsDirAppLight = 'train4_occlusion_10k'
gtDir = 'groundtruth/' + gtPrefix + '/'
featuresDir = gtDir

experimentDir = 'experiments/' + experimentPrefix + '/'
trainModelsDirPose = 'experiments/' + trainPrefixPose + '/'
trainModelsDirVColor = 'experiments/' + trainPrefixVColor + '/'
trainModelsDirLightCoeffs = 'experiments/' + trainPrefixLightCoeffs + '/'
trainModelsDirAppLight = 'experiments/' + trainModelsDirAppLight + '/'
resultDir = 'results/' + testPrefix + '/'

ignoreGT = True
ignore = []
if os.path.isfile(gtDir + 'ignore.npy'):
    ignore = np.load(gtDir + 'ignore.npy')

groundTruthFilename = gtDir + 'groundTruth.h5'
gtDataFile = h5py.File(groundTruthFilename, 'r')

numTests = 2
testSet = np.load(experimentDir + 'test.npy')[:numTests]
# testSet = np.load(experimentDir + 'test.npy')[[ 3,  5, 14, 21, 35, 36, 54, 56, 59, 60, 68, 70, 72, 79, 83, 85, 89,94]]
# [13:14]

#Bad samples for data set train5 out normal.
# testSet = np.array([162371, 410278, 132297, 350815, 104618, 330181,  85295,  95047,
#        410233, 393785, 228626, 452094, 117242,  69433,  35352,  31030,
#        268444, 147111, 117287, 268145, 478618, 334784])

shapeGT = gtDataFile[gtPrefix].shape
boolTestSet = np.zeros(shapeGT).astype(np.bool)
boolTestSet[testSet] = True
testGroundTruth = gtDataFile[gtPrefix][boolTestSet]
groundTruthTest = np.zeros(shapeGT, dtype=testGroundTruth.dtype)
groundTruthTest[boolTestSet] = testGroundTruth
groundTruth = groundTruthTest[testSet]
dataTeapotIdsTest = groundTruth['trainTeapotIds']
test = np.arange(len(testSet))

# testSamplesIds= [2]
# test = np.array([],dtype=np.uint16)
# for testId in testSamplesIds:
#     test = np.append(test, np.where(dataTeapotIdsTest == testId))
#
# groundTruth = groundTruth[test]
#

testSet = testSet[test]

print("Reading experiment.")
dataAzsGT = groundTruth['trainAzsGT']
dataObjAzsGT = groundTruth['trainObjAzsGT']
dataElevsGT = groundTruth['trainElevsGT']
dataLightAzsGT = groundTruth['trainLightAzsGT']
dataLightElevsGT = groundTruth['trainLightElevsGT']
dataLightIntensitiesGT = groundTruth['trainLightIntensitiesGT']
dataVColorGT = groundTruth['trainVColorGT']
dataScenes = groundTruth['trainScenes']
dataTeapotIds = groundTruth['trainTeapotIds']
dataEnvMaps = groundTruth['trainEnvMaps']
dataOcclusions = groundTruth['trainOcclusions']
dataTargetIndices = groundTruth['trainTargetIndices']
dataComponentsGT = groundTruth['trainComponentsGT']
dataComponentsGTRel = groundTruth['trainComponentsGTRel']
dataLightCoefficientsGT = groundTruth['trainLightCoefficientsGT']
dataLightCoefficientsGTRel = groundTruth['trainLightCoefficientsGTRel']
dataAmbientIntensityGT = groundTruth['trainAmbientIntensityGT']
dataIds = groundTruth['trainIds']

gtDtype = groundTruth.dtype

# testSet = np.array([ 11230, 3235, 10711,  9775, 11230, 10255,  5060, 12784,  5410,  1341,14448, 12935, 13196,  6728,  9002,  7946,  1119,  5827,  4842,12435,  8152,  4745,  9512,  9641,  7165, 13950,  3567,   860,4105, 10330,  7218, 10176,  2310,  5325])

testSetFixed = testSet
whereBad = []
for test_it, test_id in enumerate(testSet):
    if test_id in ignore:
        bad = np.where(testSetFixed==test_id)
        testSetFixed = np.delete(testSetFixed, bad)
        whereBad = whereBad + [bad]

# testSet = testSetFixed

loadFromHdf5 = False

syntheticGroundtruth = True

synthPrefix = '_cycles'
if syntheticGroundtruth:
    synthPrefix = ''

if syntheticGroundtruth:
    imagesDir = gtDir + 'images_opendr/'
else:
    imagesDir = gtDir + 'images/'
images = readImages(imagesDir, dataIds, loadFromHdf5)

print("Backprojecting and fitting estimates.")
# testSet = np.arange(len(images))[0:10]

testAzsGT = dataAzsGT
testObjAzsGT = dataObjAzsGT
testElevsGT = dataElevsGT
testLightAzsGT = dataLightAzsGT
testLightElevsGT = dataLightElevsGT
testLightIntensitiesGT = dataLightIntensitiesGT
testVColorGT = dataVColorGT
testComponentsGT = dataComponentsGT
testComponentsGTRel = dataComponentsGTRel

testLightCoefficientsGTRel = dataLightCoefficientsGTRel * dataAmbientIntensityGT[:,None]

testAzsRel = np.mod(testAzsGT - testObjAzsGT, 2*np.pi)

# loadHogFeatures = True
# loadZernikeFeatures = False
#
# if loadHogFeatures:
#     hogfeatures = np.load(featuresDir  +  'hog' + synthPrefix + '.npy')
#
# if loadZernikeFeatures:
#     numCoeffs=100
#     win=40
#     zernikefeatures = np.load(featuresDir  + 'zernike_numCoeffs' + str(numCoeffs) + '_win' + str(win) + synthPrefix + '.npy')
#
# testHogfeatures = hogfeatures[testSet]
# testZernikefeatures = zernikefeatures[testSet]
# testIllumfeatures = illumfeatures[testSet]

recognitionTypeDescr = ["near", "mean", "sampling"]
recognitionType = 1

optimizationTypeDescr = ["predict", "optimize", "joint"]
optimizationType = 1
computePredErrorFuns = True

method = 1
model = 1
maxiter = 500
numSamples = 1

# free_variables = [ chAz, chEl]
free_variables = [ chAz, chEl, chVColors, chLightSHCoeffs]
# free_variables = [ chAz, chEl]

mintime = time.time()
boundEl = (-np.pi, np.pi)
boundAz = (-3*np.pi, 3*np.pi)
boundscomponents = (0,None)
bounds = [boundAz,boundEl]
bounds = [(None , None ) for sublist in free_variables for item in sublist]

methods = ['dogleg', 'minimize', 'BFGS', 'L-BFGS-B', 'Nelder-Mead', 'SGDMom']

options = {'disp':False, 'maxiter':maxiter, 'lr':0.0001, 'momentum':0.1, 'decay':0.99}
options = {'disp':False, 'maxiter':maxiter}
# options={'disp':False, 'maxiter':maxiter}
# testRenderer = np.int(dataTeapotIds[testSet][0])
# testRenderer = np.int(dataTeapotIds[0])
testRenderer = 0

# testRenderer = 2
renderer = renderer_teapots[testRenderer]
nearGTOffsetRelAz = 0
nearGTOffsetEl = 0
nearGTOffsetLighCoeffs = np.zeros(9)
nearGTOffsetVColor = np.zeros(3)

#Load trained recognition models
nnBatchSize = 100

# hogGT, hogImGT, drconv = image_processing.diffHog(rendererGT)
# hogRenderer, hogImRenderer, _ = image_processing.diffHog(renderer, drconv)
#
# hogE_raw = hogGT - hogRenderer
# hogCellErrors = ch.sum(hogE_raw*hogE_raw, axis=2)
# hogError = ch.SumOfSquares(hogE_raw)

azsPredictions = np.array([])

if 'neuralNetPose' in parameterRecognitionModels:
    poseModel = ""
    with open(trainModelsDirPose + 'neuralNetModelPose.pickle', 'rb') as pfile:
        neuralNetModelPose = pickle.load(pfile)

    meanImage = neuralNetModelPose['mean']
    modelType = neuralNetModelPose['type']
    param_values = neuralNetModelPose['params']
    grayTestImages =  0.3*images[:,:,:,0] +  0.59*images[:,:,:,1] + 0.11*images[:,:,:,2]
    grayTestImages = grayTestImages[:,None, :,:]

    grayTestImages = grayTestImages - meanImage

    network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
    posePredictionFun = lasagne_nn.get_prediction_fun(network)

    posePredictions = np.zeros([len(grayTestImages), 4])
    for start_idx in range(0, max(len(grayTestImages) - nnBatchSize,0) + 1, nnBatchSize):
        posePredictions[start_idx:start_idx + nnBatchSize] = posePredictionFun(grayTestImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])
    # posePredictions = posePredictionFun(grayTestImages.astype(np.float32))

    cosAzsPred = posePredictions[:,0]
    sinAzsPred = posePredictions[:,1]
    cosElevsPred = posePredictions[:,2]
    sinElevsPred = posePredictions[:,3]

    ##Get predictions with dropout on to get samples.
    with open(trainModelsDirPose + 'neuralNetModelPose.pickle', 'rb') as pfile:
        neuralNetModelPose = pickle.load(pfile)

    meanImage = neuralNetModelPose['mean']
    modelType = neuralNetModelPose['type']
    param_values = neuralNetModelPose['params']
    grayTestImages =  0.3*images[:,:,:,0] +  0.59*images[:,:,:,1] + 0.11*images[:,:,:,2]
    grayTestImages = grayTestImages[:,None, :,:]
    grayTestImages = grayTestImages - meanImage

    # network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
    nonDetPosePredictionFun = lasagne_nn.get_prediction_fun_nondeterministic(network)
    posePredictionsSamples = []
    cosAzsPredSamples = []
    sinAzsPredSamples = []
    for i in range(100):
        posePredictionsSample = np.zeros([len(grayTestImages), 4])
        for start_idx in range(0, max(len(grayTestImages) - nnBatchSize,0) + 1, nnBatchSize):
            posePredictionsSample[start_idx:start_idx + nnBatchSize] = nonDetPosePredictionFun(grayTestImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

        cosAzsPredSample = posePredictionsSample[:,0]
        sinAzsPredSample = posePredictionsSample[:,1]
        cosAzsPredSamples = cosAzsPredSamples + [cosAzsPredSample[:,None]]
        sinAzsPredSamples = sinAzsPredSamples + [sinAzsPredSample[:,None]]

    cosAzsPredSamples = np.hstack(cosAzsPredSamples)
    sinAzsPredSamples = np.hstack(sinAzsPredSamples)

    azsPredictions = np.arctan2(sinAzsPredSamples, cosAzsPredSamples)

if 'neuralNetApperanceAndLight' in parameterRecognitionModels:
    nnModel = ""
    with open(trainModelsDirAppLight + 'neuralNetModelAppLight.pickle', 'rb') as pfile:
        neuralNetModelAppLight = pickle.load(pfile)

    meanImage = neuralNetModelAppLight['mean']
    modelType = neuralNetModelAppLight['type']
    param_values = neuralNetModelAppLight['params']

    testImages = images.reshape([images.shape[0],3,images.shape[1],images.shape[2]]) - meanImage.reshape([1,meanImage.shape[2], meanImage.shape[0],meanImage.shape[1]]).astype(np.float32)

    network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
    appLightPredictionFun = lasagne_nn.get_prediction_fun(network)

    appLightPredictions = np.zeros([len(testImages), 12])
    for start_idx in range(0, max(len(testImages) - nnBatchSize + 1,1), nnBatchSize):
        appLightPredictions[start_idx:start_idx + nnBatchSize] = appLightPredictionFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

    # appLightPredictions = appLightPredictionFun(testImages.astype(np.float32))
    relLightCoefficientsGTPred = appLightPredictions[:,:9]
    vColorsPred = appLightPredictions[:,9:]

    #Samples:
    vColorsPredSamples = []
    appLightPredictionNonDetFun = lasagne_nn.get_prediction_fun_nondeterministic(network)

    for i in range(100):
        appLightPredictions = np.zeros([len(testImages), 12])
        for start_idx in range(0, max(len(testImages) - nnBatchSize + 1,1), nnBatchSize):
            appLightPredictions[start_idx:start_idx + nnBatchSize] = appLightPredictionNonDetFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

        # appLightPredictions = appLightPredictionFun(testImages.astype(np.float32))
        # relLightCoefficientsGTPred = appLightPredictions[:,:9]
        # vColorsPred =

        vColorsPredSamples = vColorsPredSamples + [appLightPredictions[:,9:][:,:,None]]

    vColorsPredSamples = np.concatenate(vColorsPredSamples, axis=2)

if 'neuralNetVColors' in parameterRecognitionModels:
    nnModel = ""
    with open(trainModelsDirVColor + 'neuralNetModelAppearance.pickle', 'rb') as pfile:
        neuralNetModelAppearance = pickle.load(pfile)

    meanImage = neuralNetModelAppearance['mean']
    modelType = neuralNetModelAppearance['type']
    param_values = neuralNetModelAppearance['params']

    testImages = images.reshape([images.shape[0],3,images.shape[1],images.shape[2]]) - meanImage.reshape([1,meanImage.shape[2], meanImage.shape[0],meanImage.shape[1]]).astype(np.float32)

    network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
    appPredictionFun = lasagne_nn.get_prediction_fun(network)

    appPredictions = np.zeros([len(grayTestImages), 3])
    for start_idx in range(0, max(len(grayTestImages) - nnBatchSize,0) + 1, nnBatchSize):
        appPredictions[start_idx:start_idx + nnBatchSize] = appPredictionFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

    vColorsPred = appPredictions

    #Samples:
    vColorsPredSamples = []
    appPredictionNonDetFun = lasagne_nn.get_prediction_fun_nondeterministic(network)

    for i in range(100):
        appPredictions = np.zeros([len(testImages), 3])
        for start_idx in range(0, max(len(testImages) - nnBatchSize + 1,1), nnBatchSize):
            appPredictions[start_idx:start_idx + nnBatchSize] = appPredictionNonDetFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

        vColorsPredSamples = vColorsPredSamples + [appPredictions[:,:][:,:,None]]

    vColorsPredSamples = np.concatenate(vColorsPredSamples, axis=2)

if 'randForestAzs' in parameterRecognitionModels:
    with open(trainModelsDirPose + 'randForestModelCosAzs.pickle', 'rb') as pfile:
        randForestModelCosAzs = pickle.load(pfile)['randForestModelCosAzs']
    cosAzsPred = recognition_models.testRandomForest(randForestModelCosAzs, testHogfeatures)
    cosAzsPredictions = np.vstack([estimator.predict(testHogfeatures) for estimator in randForestModelCosAzs.estimators_])

    with open(trainModelsDirPose + 'randForestModelSinAzs.pickle', 'rb') as pfile:
        randForestModelSinAzs = pickle.load(pfile)['randForestModelSinAzs']
    sinAzsPred = recognition_models.testRandomForest(randForestModelSinAzs, testHogfeatures)
    sinAzsPredictions = np.vstack([estimator.predict(testHogfeatures) for estimator in randForestModelSinAzs.estimators_])

if 'randForestElevs' in parameterRecognitionModels:
    with open(trainModelsDirPose + 'randForestModelCosElevs.pickle', 'rb') as pfile:
        randForestModelCosElevs = pickle.load(pfile)['randForestModelCosElevs']
    cosElevsPred = recognition_models.testRandomForest(randForestModelCosElevs, testHogfeatures)

    cosElevsPredictions = np.vstack([estimator.predict(testHogfeatures) for estimator in randForestModelCosElevs.estimators_])

    with open(trainModelsDirPose + 'randForestModelSinElevs.pickle', 'rb') as pfile:
        randForestModelSinElevs = pickle.load(pfile)['randForestModelSinElevs']
    sinElevsPred = recognition_models.testRandomForest(randForestModelSinElevs, testHogfeatures)
    sinElevsPredictions = np.vstack([estimator.predict(testHogfeatures) for estimator in randForestModelSinElevs.estimators_])

if 'randForestVColors' in parameterRecognitionModels:
    with open(trainModelsDirVColor + 'randForestModelVColor.pickle', 'rb') as pfile:
        randForestModelVColor = pickle.load(pfile)

    colorWindow = 30
    image = images[0]
    croppedImages = images[:,image.shape[0]/2-colorWindow:image.shape[0]/2+colorWindow,image.shape[1]/2-colorWindow:image.shape[1]/2+colorWindow,:]
    vColorsPred = recognition_models.testRandomForest(randForestModelVColor, croppedImages.reshape([len(testSet),-1]))

if 'linearRegressionVColors' in parameterRecognitionModels:
    with open(trainModelsDirVColor + 'linearRegressionModelVColor.pickle', 'rb') as pfile:
        linearRegressionModelVColor = pickle.load(pfile)

    colorWindow = 30
    image = images[0]
    croppedImages = images[:,image.shape[0]/2-colorWindow:image.shape[0]/2+colorWindow,image.shape[1]/2-colorWindow:image.shape[1]/2+colorWindow,:]
    vColorsPred = recognition_models.testLinearRegression(linearRegressionModelVColor, croppedImages.reshape([len(testSet),-1]))

if 'medianVColors' in parameterRecognitionModels:
    # recognition_models.medianColor(image, win)
    colorWindow = 30
    imagesWin = images[:,images.shape[1]/2-colorWindow:images.shape[1]/2+colorWindow,images.shape[2]/2-colorWindow:images.shape[2]/2+colorWindow,:]
    vColorsPred = np.median(imagesWin.reshape([images.shape[0],-1,3]), axis=1)/1.4
    # return color

# import theano
# import theano.tensor as T
SHModel = ""
# ## Theano NN error function 1.
# with open(trainModelsDirPose + 'neuralNetModelPose.pickle', 'rb') as pfile:
#     neuralNetModelPose = pickle.load(pfile)
#
# meanImage = neuralNetModelPose['mean'].reshape([150,150])
#
# modelType = neuralNetModelPose['type']
# param_values = neuralNetModelPose['params']
# network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
# layer = lasagne.layers.get_all_layers(network)[-2]
# inputLayer = lasagne.layers.get_all_layers(network)[0]
# layer_output = lasagne.layers.get_output(layer, deterministic=True)
# dim_output= layer.output_shape[1]
#
# networkGT = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
# layerGT = lasagne.layers.get_all_layers(networkGT)[-2]
# inputLayerGT = lasagne.layers.get_all_layers(networkGT)[0]
# layer_outputGT = lasagne.layers.get_output(layerGT, deterministic=True)
#
# rendererGray =  0.3*renderer[:,:,0] +  0.59*renderer[:,:,1] + 0.11*renderer[:,:,2]
# rendererGrayGT =  0.3*rendererGT[:,:,0] +  0.59*rendererGT[:,:,1] + 0.11*rendererGT[:,:,2]
#
# chThError = TheanoFunOnOpenDR(theano_input=inputLayer.input_var, theano_output=layer_output, opendr_input=rendererGray - meanImage, dim_output = dim_output,
#                               theano_input_gt=inputLayerGT.input_var, theano_output_gt=layer_outputGT, opendr_input_gt=rendererGrayGT - meanImage)
#
# chThError.compileFunctions(layer_output, theano_input=inputLayer.input_var, dim_output=dim_output, theano_input_gt=inputLayerGT.input_var, theano_output_gt=layer_outputGT)
#
# chThError.r

## Theano NN error function 2.
# with open(trainModelsDirPose + 'neuralNetModelPoseLarge.pickle', 'rb') as pfile:
#     neuralNetModelPose = pickle.load(pfile)
#
# meanImage = neuralNetModelPose['mean'].reshape([150,150])

# modelType = neuralNetModelPose['type']
# param_values = neuralNetModelPose['params']
# network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
# layer = lasagne.layers.get_all_layers(network)[-2]
# inputLayer = lasagne.layers.get_all_layers(network)[0]
# layer_output = lasagne.layers.get_output(layer, deterministic=True)
# dim_output= layer.output_shape[1]
#
# networkGT = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
# layerGT = lasagne.layers.get_all_layers(networkGT)[-2]
# inputLayerGT = lasagne.layers.get_all_layers(networkGT)[0]
# layer_outputGT = lasagne.layers.get_output(layerGT, deterministic=True)
#
# chThError8 = TheanoFunOnOpenDR(theano_input=inputLayer.input_var, theano_output=layer_output, opendr_input=rendererGray - meanImage, dim_output = dim_output,
#                               theano_input_gt=inputLayerGT.input_var, theano_output_gt=layer_outputGT, opendr_input_gt=rendererGrayGT - meanImage)
#
# chThError8.compileFunctions(layer_output, theano_input=inputLayer.input_var, dim_output=dim_output, theano_input_gt=inputLayerGT.input_var, theano_output_gt=layer_outputGT)
#
# chThError8.r


# chNNAz = 2*ch.arctan(chThSHFun[1]/(ch.sqrt(chThSHFun[0]**2 + chThSHFun[1]**2) + chThSHFun[0]))
# chNNEl = 2*ch.arctan(chThSHFun[3]/(ch.sqrt(chThSHFun[2]**2 + chThSHFun[3]**2) + chThSHFun[2]))
#
# chNNAzGT = 2*ch.arctan(chThSHFunGT[1]/(ch.sqrt(chThSHFunGT[0]**2 + chThSHFunGT[1]**2) + chThSHFunGT[0]))
# chNNElGT = 2*ch.arctan(chThSHFunGT[3]/(ch.sqrt(chThSHFunGT[2]**2 + chThSHFunGT[3]**2) + chThSHFunGT[2]))

# nnPoseError = ch.sum((chThFun - chThFunGT)**2)

if 'neuralNetModelSHLight' in parameterRecognitionModels:
    nnModel = ""
    with open(trainModelsDirLightCoeffs + 'neuralNetModelLight.pickle', 'rb') as pfile:
        neuralNetModelSHLight = pickle.load(pfile)

    meanImage = neuralNetModelSHLight['mean']
    modelType = neuralNetModelSHLight['type']
    param_values = neuralNetModelSHLight['params']

    testImages = images.reshape([images.shape[0],3,images.shape[1],images.shape[2]]) - meanImage.reshape([1,meanImage.shape[2], meanImage.shape[0],meanImage.shape[1]]).astype(np.float32)

    network = lasagne_nn.load_network(modelType=modelType, param_values=param_values)
    lightPredictionFun = lasagne_nn.get_prediction_fun(network)

    appPredictions = np.zeros([len(grayTestImages), 9])
    for start_idx in range(0, max(len(grayTestImages) - nnBatchSize,0) + 1, nnBatchSize):
        appPredictions[start_idx:start_idx + nnBatchSize] = lightPredictionFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])

    relLightCoefficientsGTPred = appPredictions

    # #Samples:
    # vColorsPredSamples = []
    # appPredictionNonDetFun = lasagne_nn.get_prediction_fun_nondeterministic(network)
    #
    # for i in range(100):
    #     appPredictions = np.zeros([len(testImages), 3])
    #     for start_idx in range(0, max(len(testImages) - nnBatchSize + 1,1), nnBatchSize):
    #         appPredictions[start_idx:start_idx + nnBatchSize] = appPredictionNonDetFun(testImages.astype(np.float32)[start_idx:start_idx + nnBatchSize])
    #
    #     vColorsPredSamples = vColorsPredSamples + [appPredictions[:,:][:,:,None]]
    #
    # vColorsPredSamples = np.concatenate(vColorsPredSamples, axis=2)


if 'randomForestSHZernike' in parameterRecognitionModels:

    SHModel = 'randomForestSHZernike'
    with open(trainModelsDirLightCoeffs  + 'randomForestModelZernike' + str(numCoeffs) + '_win' + str(win) + '.pickle', 'rb') as pfile:
        randForestModelLightCoeffs = pickle.load(pfile)

    relLightCoefficientsGTPred = recognition_models.testRandomForest(randForestModelLightCoeffs, testZernikefeatures)

if 'meanSHLight' in parameterRecognitionModels:
    SHModel = 'meanSHLight'
    relLightCoefficientsGTPred = np.tile(np.array([  7.85612876e-01,  -8.33688916e-03,   2.42002031e-01,
         6.63450677e-03,  -7.45523901e-04,   2.82965294e-03,
         3.09943249e-01,  -1.15105810e-03,  -3.26439948e-03])[None,:], [testLightCoefficientsGTRel.shape[0],1])

if 'constantSHLight' in parameterRecognitionModels:
    SHModel = 'Constant'
    relLightCoefficientsGTPred = np.tile(np.array([  0.75,  0,   0.15, 0,  0,   0, 0,  0,  0])[None,:], [testLightCoefficientsGTRel.shape[0],1])

if 'linRegModelSHZernike' in parameterRecognitionModels:
    with open(trainModelsDirLightCoeffs  + 'linRegModelZernike' + str(numCoeffs) + '_win' + str(win) + '.pickle', 'rb') as pfile:
        linearRegressionModelLightCoeffs = pickle.load(pfile)

    relLightCoefficientsGTPred = recognition_models.testLinearRegression(linearRegressionModelLightCoeffs, testZernikefeatures)

if not os.path.exists(resultDir + 'imgs/'):
    os.makedirs(resultDir + 'imgs/')
if not os.path.exists(resultDir +  'imgs/samples/'):
    os.makedirs(resultDir + 'imgs/samples/')

print("Finished loading and compiling recognition models")

elevsPred = np.arctan2(sinElevsPred, cosElevsPred)
azsPred = np.arctan2(sinAzsPred, cosAzsPred)

## NN prediction samples analysis.


# directory = resultDir
# plt.ioff()
# fig = plt.figure()
# errorFun = models[0]
# for test_i, sampleAzsPredictions in enumerate(azsPredictions):
#
#     testId = dataIds[test_i]
#
#     rendererGT[:] = srgb2lin(images[test_i])
#
#     testnum = (test_i + 1)*2
#
#     plt.scatter(np.ones_like(sampleAzsPredictions)*testnum, np.mod(sampleAzsPredictions*180/np.pi, 360), c='b')
#
#     bestAzErr = np.finfo('f').max
#     bestAz = testAzsRel[test_i]
#     bestAzNormalErr = np.finfo('f').max
#     bestAzNormal = testAzsRel[test_i]
#     for sample_i in range(len(testAzsRel)):
#
#         color = testVColorGT[test_i]
#         az =  sampleAzsPredictions[sample_i]
#         el = testElevsGT[test_i]
#         lightCoefficientsRel = testLightCoefficientsGTRel[test_i]
#         chAz[:] = az
#         chEl[:] = el
#         chVColors[:] = color
#         chLightSHCoeffs[:] = lightCoefficientsRel
#         if chThError.r < bestAzErr:
#             bestAzErr = chThError.r
#             bestAz = az
#         if errorFun.r < bestAzNormalErr:
#             bestAzNormalErr = errorFun.r
#             bestAzNormal = az
#
#     from sklearn import mixture
#     # gmm = mixture.GMM(n_components=5, covariance_type='spherical', min_covar=radians(5)**2, init_params='wmc', params='wmc')
#
#     # gmm.fit(np.hstack([sinAzsPredictions[:,sample_i][:,None], cosAzsPredictions[:,sample_i][:,None]]))
#     # azsGmms = azsGmms + [gmm]
#     # for comp_i, weight in enumerate(gmm.weights_):
#     #     meanSin = gmm.means_[comp_i][0]
#     #     meanCos = gmm.means_[comp_i][1]
#     #     azCompMean = np.arctan2(meanSin, meanCos)
#     #     plt.plot(sample-0.4, np.mod(azCompMean*180/np.pi, 360), marker='o', ms=weight*50, c='y')
#     plt.plot(testnum,np.mod(bestAzNormal*180/np.pi,360), marker='o', ms=20, c='purple')
#     plt.plot(testnum,np.mod(bestAz*180/np.pi,360), marker='o', ms=20, c='y')
#     plt.plot(testnum,testAzsRel[test_i]*180/np.pi, marker='o', ms=20, c='g')
#     plt.plot(testnum, np.mod(azsPred[test_i]*180/np.pi, 360), marker='o', ms=20, c='r')
#
# plt.xlabel('Sample')
# plt.ylabel('Angular error')
# x1,x2,y1,y2 = plt.axis()
# plt.axis((0,len(testSet+1)*2,0,360))
# plt.title('Neuralnet multiple predictions')
# fig.savefig(directory + 'neuralNet_Az_scatter.png', bbox_inches='tight')
# plt.close(fig)
# # elsPredictions = [np.arctan2(sinElsPredictions[i], cosAzsPredictions[i]) for i in range(len(cosAzsPredictions))]
#
#

## NN individual prediction samples analysis.
if not os.path.exists(resultDir + 'nn_samples/'):
    os.makedirs(resultDir + 'nn_samples/')

if not os.path.exists(resultDir + 'az_samples/'):
    os.makedirs(resultDir + 'az_samples/')

if not os.path.exists(resultDir + 'hue_samples/'):
    os.makedirs(resultDir + 'hue_samples/')

analyzeSamples = False

def analyzeHue(figurePath, rendererGT, renderer, sampleEl, sampleAz, sampleSH, sampleVColorsPredictions=None, sampleStds=0.1):
    global stds
    global chAz
    global test_i
    global samplingMode

    plt.ioff()
    fig = plt.figure()

    stds[:] = sampleStds
    negLikModel = -ch.sum(generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances))/numPixels
    negLikModelRobust = -ch.sum(generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances))/numPixels
    models = [negLikModel, negLikModelRobust, negLikModelRobust]
    errorFunRobust = models[1]
    errorFunGaussian = models[0]

    vColorsPredSamplesHSV = cv2.cvtColor(np.uint8(sampleVColorsPredictions.reshape([1, 100, 3])*255), cv2.COLOR_RGB2HSV)[0,:,0]

    plt.hist(vColorsPredSamplesHSV, bins=30, alpha=0.2)

    hueGT = cv2.cvtColor(np.uint8(testVColorGT[test_i][None,None,:]*255), cv2.COLOR_RGB2HSV)[0,0,0]
    huePred = cv2.cvtColor(np.uint8(vColorsPred[test_i][None,None,:]*255), cv2.COLOR_RGB2HSV)[0,0,0]

    chAz[:] = sampleAz
    chEl[:] = sampleEl
    currentVColors = chVColors.r
    currentHSV = cv2.cvtColor(np.uint8(currentVColors[None,None,:]*255), cv2.COLOR_RGB2HSV)[0,0]

    chLightSHCoeffs[:] = sampleSH

    trainingTeapots = [0]
    hueRange = np.arange(0,255,5)
    # chThErrors = np.zeros([len(trainingTeapots), len(hueRange)])

    robustErrors = np.array([])
    gaussianErrors = np.array([])
    hues = np.array([])
    for hue_i, hue in enumerate(hueRange):
        hues = np.append(hues, hue)

        color = cv2.cvtColor(np.array([hue, currentHSV[1],currentHSV[2]])[None,None,:].astype(np.uint8), cv2.COLOR_HSV2RGB)/255
        chVColors[:] = color

        for idx, renderer_idx in enumerate(trainingTeapots):
            renderer_i = renderer_teapots[renderer_idx]
            rendererGray =  0.3*renderer_i[:,:,0] +  0.59*renderer_i[:,:,1] + 0.11*renderer_i[:,:,2]
            # chThError.opendr_input = rendererGray
            # chThErrors[idx, az_i] = chThError.r

        robustErrors = np.append(robustErrors, errorFunRobust.r)
        gaussianErrors = np.append(gaussianErrors, errorFunGaussian.r)

    x1,x2,y1,y2 = plt.axis()

    robustErrors = robustErrors - np.min(robustErrors)
    gaussianErrors = gaussianErrors - np.min(gaussianErrors)
    # chThErrors = chThErrors - np.min(chThErrors)
    plt.plot(hues, robustErrors*y2/np.max(robustErrors),  c='brown')
    plt.plot(hues, gaussianErrors*y2/np.max(gaussianErrors),  c='purple')

    chThError.opendr_input = renderer
    lineStyles = ['-', '--', '-.', ':']

    # plt.axvline(np.mod(bestAzNormal*180/np.pi,360), linewidth=2, c='purple')
    # plt.axvline(np.mod(bestAzRobust*180/np.pi,360), linewidth=2, c='brown')
    # plt.axvline(bestHue, linewidth=2, c='y')
    plt.axvline(hueGT, linewidth=2,c='g')
    plt.axvline(huePred, linewidth=2,c='r')

    # plt.axvline(np.mod(currentAz*180/np.pi, 360), linewidth=2, linestyle='--',c='b')

    plt.xlabel('Sample')
    plt.ylabel('Angular error')

    plt.axis((0,255,y1,y2))
    plt.title('Neuralnet multiple predictions')
    fig.savefig(figurePath + 'sample' + '.png', bbox_inches='tight')
    plt.close(fig)

    chVColors[:] = currentVColors
    cv2.imwrite(figurePath + '_render.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))


def analyzeAz(figurePath, rendererGT, renderer, sampleEl, sampleVColor, sampleSH, sampleAzsPredictions=None, sampleStds=0.1):
    global stds
    global chAz
    global test_i
    global samplingMode

    plt.ioff()
    fig = plt.figure()

    stds[:] = sampleStds
    negLikModel = -ch.sum(generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances))/numPixels
    negLikModelRobust = -ch.sum(generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances))/numPixels
    models = [negLikModel, negLikModelRobust, negLikModelRobust]
    errorFunRobust = models[1]
    errorFunGaussian = models[0]

    plt.hist(np.mod(sampleAzsPredictions*180/np.pi,360), bins=30, alpha=0.2)

    bestAz = testAzsRel[test_i]

    currentAz = chAz.r.copy()
    chEl[:] = sampleEl
    chVColors[:] = sampleVColor
    chLightSHCoeffs[:] = sampleSH

    trainingTeapots = [0,14,20,25,26,1]
    trainingTeapots = [0]
    azRange = np.arange(0,2*np.pi,5*np.pi/180)
    chThErrors = np.zeros([len(trainingTeapots), len(azRange)])

    robustErrors = np.array([])
    gaussianErrors = np.array([])
    angles = np.array([])
    for az_i, az in enumerate(azRange):
        angles = np.append(angles, az*180/np.pi)
        chAz[:] = az
        for idx, renderer_idx in enumerate(trainingTeapots):
            renderer_i = renderer_teapots[renderer_idx]
            rendererGray =  0.3*renderer_i[:,:,0] +  0.59*renderer_i[:,:,1] + 0.11*renderer_i[:,:,2]
            chThError.opendr_input = rendererGray
            chThErrors[idx, az_i] = chThError.r

        robustErrors = np.append(robustErrors, errorFunRobust.r)
        gaussianErrors = np.append(gaussianErrors, errorFunGaussian.r)

    x1,x2,y1,y2 = plt.axis()

    robustErrors = robustErrors - np.min(robustErrors)
    gaussianErrors = gaussianErrors - np.min(gaussianErrors)
    chThErrors = chThErrors - np.min(chThErrors)
    plt.plot(angles, robustErrors*y2/np.max(robustErrors),  c='brown')
    plt.plot(angles, gaussianErrors*y2/np.max(gaussianErrors),  c='purple')

    chThError.opendr_input = renderer
    lineStyles = ['-', '--', '-.', ':']
    for renderer_idx in range(len(trainingTeapots)):
        plt.plot(angles, chThErrors[renderer_idx]*y2/np.max(chThErrors[renderer_idx]), linestyle=lineStyles[np.mod(renderer_idx,4)], c='y')

    if len(trainingTeapots) > 1:
        prodErrors = np.prod(chThErrors, axis=0)
        plt.plot(angles, prodErrors*y2/np.max(prodErrors), linestyle='-', c='black')
        meanErrors = np.mean(chThErrors, axis=0)
        plt.plot(angles, meanErrors*y2/np.max(meanErrors), linestyle='--', c='black')
        # plt.plot(angles, gaussianErrors*robustErrors*y2/np.max(gaussianErrors*robustErrors), linestyle='--', c='black')

    # plt.axvline(np.mod(bestAzNormal*180/np.pi,360), linewidth=2, c='purple')
    # plt.axvline(np.mod(bestAzRobust*180/np.pi,360), linewidth=2, c='brown')
    plt.axvline(np.mod(bestAz*180/np.pi,360), linewidth=2, c='y')
    plt.axvline(testAzsRel[test_i]*180/np.pi, linewidth=2,c='g')
    plt.axvline(np.mod(azsPred[test_i]*180/np.pi, 360), linewidth=2,c='r')

    plt.axvline(np.mod(currentAz*180/np.pi, 360), linewidth=2, linestyle='--',c='b')


    plt.xlabel('Sample')
    plt.ylabel('Angular error')

    if samplingMode == False:

        scaleAzSamples = np.array(errorFunAzSamples)
        scaleAzSamples = scaleAzSamples - np.min(scaleAzSamples) + 1
        scaleAzSamples = scaleAzSamples*0.25*y2/np.max(scaleAzSamples)
        for azSample_i, azSample in enumerate(scaleAzSamples):
            plt.plot(np.mod(totalAzSamples[azSample_i]*180/np.pi, 360), azSample, marker='o', ms=5., c='r')

        scaleAzSamples = np.array(errorFunGaussianAzSamples)
        scaleAzSamples = scaleAzSamples - np.min(scaleAzSamples) + 1
        scaleAzSamples = scaleAzSamples*0.4*y2/np.max(scaleAzSamples)
        for azSample_i, azSample in enumerate(scaleAzSamples):
            plt.plot(np.mod(totalAzSamples[azSample_i]*180/np.pi, 360), azSample, marker='o', ms=5., c='g')

        scaleAzSamples = np.array(errorFunAzSamplesPred)
        scaleAzSamples = scaleAzSamples - np.min(scaleAzSamples) + 1
        scaleAzSamples = scaleAzSamples*0.65*y2/np.max(scaleAzSamples)
        for azSample_i, azSample in enumerate(scaleAzSamples):
            plt.plot(np.mod(totalAzSamples[azSample_i]*180/np.pi, 360), azSample, marker='o', ms=5., c='b')

        scaleAzSamples = np.array(errorFunGaussianAzSamplesPred)
        scaleAzSamples = scaleAzSamples - np.min(scaleAzSamples) + 1
        scaleAzSamples = scaleAzSamples*0.75*y2/np.max(scaleAzSamples)
        for azSample_i, azSample in enumerate(scaleAzSamples):
            plt.plot(np.mod(totalAzSamples[azSample_i]*180/np.pi, 360), azSample, marker='o', ms=5., c='y')


    plt.axis((0,360,y1,y2))
    plt.title('Neuralnet multiple predictions')
    fig.savefig(figurePath + 'sample' + '.png', bbox_inches='tight')
    plt.close(fig)

    chAz[:] = currentAz
    cv2.imwrite(figurePath + '_render.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))


errorsPosePred = recognition_models.evaluatePrediction(testAzsRel, testElevsGT, azsPred, elevsPred)

errorsLightCoeffs = (testLightCoefficientsGTRel - relLightCoefficientsGTPred)**2
errorsVColors = (testVColorGT - vColorsPred)**2

meanAbsErrAzs = np.mean(np.abs(errorsPosePred[0]))
meanAbsErrElevs = np.mean(np.abs(errorsPosePred[1]))

medianAbsErrAzs = np.median(np.abs(errorsPosePred[0]))
medianAbsErrElevs = np.median(np.abs(errorsPosePred[1]))

meanErrorsLightCoeffs = np.sqrt(np.mean(np.mean(errorsLightCoeffs,axis=1), axis=0))
meanErrorsVColors = np.sqrt(np.mean(np.mean(errorsVColors,axis=1), axis=0))

#Fit:
print("Fitting predictions")

fittedAzs = np.array([])
fittedElevs = np.array([])
fittedRelLightCoeffs = []
fittedVColors = []

predictedErrorFuns = np.array([])
fittedErrorFuns = np.array([])

print("Using " + modelsDescr[model])
errorFun = models[model]
pixelErrorFun = pixelModels[model]

testSamples = 1
if recognitionType == 2:
    testSamples  = numSamples
predSamples = 50

chDisplacement[:] = np.array([0.0, 0.0,0.0])
chScale[:] = np.array([1.0,1.0,1.0])
chObjAz[:] = 0
shapeIm = [height, width]

#Update all error functions with the right renderers.
print("Using " + modelsDescr[model])

negLikModel = -ch.sum(generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances))/numPixels
negLikModelRobust = -ch.sum(generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances))/numPixels
pixelLikelihoodCh = generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances)
pixelLikelihoodRobustCh = generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances)
# negLikModel = -generative_models.modelLogLikelihoodCh(rendererGT, renderer, np.array([]), 'FULL', variances)/numPixels
# negLikModelRobust = -generative_models.modelLogLikelihoodRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances)/numPixels
# pixelLikelihoodCh = generative_models.logPixelLikelihoodCh(rendererGT, renderer, np.array([]), 'FULL', variances)
# pixelLikelihoodRobustCh = ch.log(generative_models.pixelLikelihoodRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances))

post = generative_models.layerPosteriorsRobustCh(rendererGT, renderer, np.array([]), 'FULL', globalPrior, variances)[0]

# hogGT, hogImGT, drconv = image_processing.diffHog(rendererGT)
# hogRenderer, hogImRenderer, _ = image_processing.diffHog(renderer, drconv)
#
# hogE_raw = hogGT - hogRenderer
# hogCellErrors = ch.sum(hogE_raw*hogE_raw, axis=2)
# hogError = ch.SumOfSquares(hogE_raw)

# models = [negLikModel, negLikModelRobust, hogError]
models = [negLikModel, negLikModelRobust, negLikModelRobust]
# pixelModels = [pixelLikelihoodCh, pixelLikelihoodRobustCh, hogCellErrors]
pixelModels = [pixelLikelihoodCh, pixelLikelihoodRobustCh, pixelLikelihoodRobustCh]
modelsDescr = ["Gaussian Model", "Outlier model", "HOG"]

# models = [negLikModel, negLikModelRobust, negLikModelRobust]
# pixelModels = [pixelLikelihoodCh, pixelLikelihoodRobustCh, pixelLikelihoodRobustCh]
# pixelErrorFun = pixelModels[model]
errorFun = models[model]

# if optimizationTypeDescr[optimizationType] != 'predict':
startTime = time.time()
samplingMode = False

testOcclusions = dataOcclusions

fittedVColorsList = []
fittedRelLightCoeffsList = []

if (computePredErrorFuns and optimizationType == 0) or optimizationType != 0:
    for test_i in range(len(testAzsRel)):

        bestFittedAz = chAz.r
        bestFittedEl = chEl.r
        bestModelLik = np.finfo('f').max
        bestVColors = chVColors.r
        bestLightSHCoeffs = chLightSHCoeffs.r

        testId = dataIds[test_i]
        print("************** Minimizing loss of prediction " + str(test_i) + "of " + str(len(testAzsRel)))

        rendererGT[:] = srgb2lin(images[test_i])

        negLikModel = -ch.sum(generative_models.LogGaussianModel(renderer=renderer, groundtruth=rendererGT, variances=variances))/numPixels
        negLikModelRobust = -ch.sum(generative_models.LogRobustModel(renderer=renderer, groundtruth=rendererGT, foregroundPrior=globalPrior, variances=variances))/numPixels
        models = [negLikModel, negLikModelRobust]

        # hogGT, hogImGT, _ = image_processing.diffHog(rendererGT, drconv)
        # hogRenderer, hogImRenderer, _ = image_processing.diffHog(renderer, drconv)
        #
        # hogE_raw = hogGT - hogRenderer
        # hogCellErrors = ch.sum(hogE_raw*hogE_raw, axis=2)
        # hogError = ch.SumOfSquares(hogE_raw)

        if not os.path.exists(resultDir + 'imgs/test'+ str(test_i) + '/'):
            os.makedirs(resultDir + 'imgs/test'+ str(test_i) + '/')

        cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/id' + str(testId) +'_groundtruth' + '.png', cv2.cvtColor(np.uint8(lin2srgb(rendererGT.r.copy())*255), cv2.COLOR_RGB2BGR))

        for sample in range(testSamples):
            from numpy.random import choice
            if recognitionType == 0:
                #Prediction from (near) ground truth.
                color = testVColorGT[test_i] + nearGTOffsetVColor
                az = testAzsRel[test_i] + nearGTOffsetRelAz
                el = testElevsGT[test_i] + nearGTOffsetEl
                lightCoefficientsRel = testLightCoefficientsGTRel[test_i]
            elif recognitionType == 1 or recognitionType == 2:
                #Point (mean) estimate:
                az = azsPred[test_i]
                el = min(max(elevsPred[test_i],radians(1)), np.pi/2-radians(1))
                # el = testElevsGT[test_i]

                color = vColorsPred[test_i]
                #
                # color = testVColorGT[test_i]

                lightCoefficientsRel = relLightCoefficientsGTPred[test_i]
                #
                # lightCoefficientsRel = testLightCoefficientsGTRel[test_i]

            chAz[:] = az
            chEl[:] = el
            chVColors[:] = color
            chLightSHCoeffs[:] = lightCoefficientsRel


            cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/sample' + str(sample) +  '_predicted'+ '.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))

            if recognitionType == 2:
                errorFunAzSamples = []
                errorFunAzSamplesPred = []
                errorFunGaussianAzSamplesPred = []
                errorFunGaussianAzSamples = []

                if not os.path.exists(resultDir + 'az_samples/test' + str(test_i) + '/'):
                    os.makedirs(resultDir + 'az_samples/test' + str(test_i) + '/')
                if not os.path.exists(resultDir + 'hue_samples/test' + str(test_i) + '/'):
                    os.makedirs(resultDir + 'hue_samples/test' + str(test_i) + '/')
                samplingMode = True
                cv2.imwrite(resultDir + 'az_samples/test' + str(test_i)  + '_gt.png', cv2.cvtColor(np.uint8(lin2srgb(rendererGT.r.copy())*255), cv2.COLOR_RGB2BGR))
                stds[:] = 0.1
                # ipdb.set_trace()
                # azSampleStdev = np.std(azsPredictions[test_i])

                azSampleStdev = np.sqrt(-np.log(np.min([np.mean(sinAzsPredSamples[test_i])**2 + np.mean(cosAzsPredSamples[test_i])**2,1])))
                predAz = chAz.r
                numSamples = max(int(np.ceil(azSampleStdev*180./(np.pi*25.))),1)
                azSamples = np.linspace(0, azSampleStdev, numSamples)
                totalAzSamples = predAz + np.concatenate([azSamples, -azSamples[1:]])
                sampleAzNum  = 0

                model = 1
                errorFun = models[model]

                bestPredAz = chAz.r
                # bestPredEl = chEl.r
                bestPredEl = min(max(chEl.r.copy(),radians(1)), np.pi/2-radians(1))
                bestPredVColors = chVColors.r.copy()
                bestPredLightSHCoeffs = chLightSHCoeffs.r.copy()
                bestModelLik = np.finfo('f').max
                bestPredModelLik = np.finfo('f').max
                # analyzeAz(resultDir + 'az_samples/test' + str(test_i) +'/pre'  , rendererGT, renderer, chEl.r, chVColors.r, chLightSHCoeffs.r, azsPredictions[test_i], sampleStds=stds.r)

                # analyzeHue(resultDir + 'hue_samples/test' + str(test_i) +'/pre', rendererGT, renderer, chEl.r, chAz.r, chLightSHCoeffs.r, vColorsPredSamples[test_i], sampleStds=stds.r)

                for sampleAz in totalAzSamples:
                    global iterat
                    iterat = 0
                    sampleAzNum += 1

                    chAz[:] = sampleAz
                    # chEl[:] = elsample
                    print("Minimizing first step")
                    model = 1
                    errorFun = models[model]
                    method = 1

                    chLightSHCoeffs[:] = lightCoefficientsRel
                    chVColors[:] = color
                    #Todo test with adding chEl.
                    free_variables = [chLightSHCoeffs]
                    options={'disp':False, 'maxiter':5}

                    errorFunAzSamplesPred = errorFunAzSamplesPred + [errorFun.r]
                    errorFunGaussianAzSamplesPred = errorFunGaussianAzSamplesPred + [models[0].r]

                    # ch.minimize({'raw': errorFun}, bounds=None, method=methods[method], x0=free_variables, callback=cb, options=options)

                    # analyzeAz(resultDir + 'az_samples/test' + str(test_i) +'/azNum' + str(sampleAzNum), rendererGT, renderer, chEl.r, chVColors.r, chLightSHCoeffs.r, azsPredictions[test_i], sampleStds=stds.r)

                    if models[1].r.copy() < bestPredModelLik:

                        print("Found best angle!")
                        # bestPredModelLik = errorFun.r.copy()
                        bestPredModelLik = models[1].r.copy()
                        bestPredAz = sampleAz
                        bestPredEl = min(max(chEl.r.copy(),radians(1)), np.pi/2-radians(1))
                        bestPredVColors = chVColors.r.copy()
                        bestPredLightSHCoeffs = chLightSHCoeffs.r.copy()
                        bestModelLik = errorFun.r.copy()

                        # cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/best_predSample' + str(numPredSamples) + '.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))

                    errorFunAzSamples = errorFunAzSamples + [errorFun.r]
                    errorFunGaussianAzSamples = errorFunGaussianAzSamples + [models[0].r]

                color = bestPredVColors
                lightCoefficientsRel = bestPredLightSHCoeffs
                az = bestPredAz

                # previousAngles = np.vstack([previousAngles, np.array([[azsample, elsample],[chAz.r.copy(), chEl.r.copy()]])])

                samplingMode = False
                chAz[:] = az
                # analyzeAz(resultDir + 'az_samples/test' + str(test_i) +'_samples', rendererGT, renderer, chEl.r, color, lightCoefficientsRel, azsPredictions[test_i], sampleStds=stds.r)

            chAz[:] = az
            chEl[:] = min(max(el,radians(1)), np.pi/2-radians(1))
            chVColors[:] = color
            chLightSHCoeffs[:] = lightCoefficientsRel.copy()

            cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/best_sample' + '.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))
            # plt.imsave(resultDir + 'imgs/test'+ str(test_i) + '/id' + str(testId) +'_groundtruth_drAz' + '.png', z.squeeze(),cmap=matplotlib.cm.coolwarm, vmin=-1, vmax=1)

            predictedErrorFuns = np.append(predictedErrorFuns, errorFun.r)

            global iterat
            iterat = 0

            sampleAzNum = 0

            sys.stdout.flush()
            if optimizationTypeDescr[optimizationType] == 'optimize':
                print("** Minimizing from initial predicted parameters. **")
                model = 1
                errorFun = models[model]
                # errorFun = chThError
                method = 1
                stds[:] = 0.1

                options={'disp':False, 'maxiter':50}
                # options={'disp':False, 'maxiter':maxiter, 'lr':0.0001, 'momentum':0.1, 'decay':0.99}
                free_variables = [ chAz, chEl, chVColors, chLightSHCoeffs]
                # free_variables = [ chAz, chEl, chVColors, chLightSHCoeffs]
                samplingMode = True

                azSampleStdev = np.sqrt(-np.log(np.min([np.mean(sinAzsPredSamples[test_i])**2 + np.mean(cosAzsPredSamples[test_i])**2,1])))
                # if azSampleStdev*180/np.pi < 100:
                ch.minimize({'raw': errorFun}, bounds=None, method=methods[method], x0=free_variables, callback=cb, options=options)

                # free_variables = [ chAz, chEl, chVColors, chLightSHCoeffs]
                # stds[:] = 0.01
                # ch.minimize({'raw': errorFun}, bounds=None, method=methods[method], x0=free_variables, callback=cb, options=options)

            if errorFun.r < bestModelLik:
                bestModelLik = errorFun.r.copy()
                bestFittedAz = chAz.r.copy()
                bestFittedEl = min(max(chEl.r.copy(),radians(1)), np.pi/2-radians(1))
                bestVColors = chVColors.r.copy()
                bestLightSHCoeffs = chLightSHCoeffs.r.copy()
                cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/best'+ '.png', cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))
            else:
                bestFittedAz = bestPredAz.copy()
                # bestFittedEl = min(max(bestPredEl.copy(),radians(1)), np.pi/2-radians(1))
                # bestVColors = bestPredVColors.copy()
                # bestLightSHCoeffs = bestPredLightSHCoeffs.copy()

            chAz[:] = bestFittedAz
            chEl[:] = min(max(bestFittedEl,radians(1)), np.pi/2-radians(1))
            chVColors[:] = bestVColors
            chLightSHCoeffs[:] = bestLightSHCoeffs

            # model=1
            # errorFun = models[model]
            # method=1
            # stds[:] = 0.1
            # options={'disp':False, 'maxiter':5}
            # free_variables = [ chAz, chEl, chVColors, chLightSHCoeffs]
            # ch.minimize({'raw': errorFun}, bounds=None, method=methods[method], x0=free_variables, callback=cb, options=options)

            cv2.imwrite(resultDir + 'imgs/test'+ str(test_i) + '/fitted'+ '.png',cv2.cvtColor(np.uint8(lin2srgb(renderer.r.copy())*255), cv2.COLOR_RGB2BGR))

        if not optimizationTypeDescr[optimizationType] == 'predict':
            fittedErrorFuns = np.append(fittedErrorFuns, bestModelLik)
            fittedAzs = np.append(fittedAzs, bestFittedAz)
            fittedElevs = np.append(fittedElevs, bestFittedEl)
            fittedVColorsList = fittedVColorsList + [bestVColors]
            fittedRelLightCoeffsList = fittedRelLightCoeffsList + [bestLightSHCoeffs]

        if optimizationTypeDescr[optimizationType] != 'predict':
            if fittedVColorsList:
                fittedVColors = np.vstack(fittedVColorsList)
            if fittedRelLightCoeffsList:
                fittedRelLightCoeffs = np.vstack(fittedRelLightCoeffsList)

        errorsPosePredSoFar = recognition_models.evaluatePrediction(testAzsRel, testElevsGT, azsPred, elevsPred)

        errorsLightCoeffsSoFar = (testLightCoefficientsGTRel[:test_i+1] - relLightCoefficientsGTPred[:test_i+1])**2
        errorsVColorsSoFar = (testVColorGT[:test_i+1] - vColorsPred[:test_i+1])**2

        meanAbsErrAzsSoFar = np.mean(np.abs(errorsPosePred[0][:test_i+1]))
        meanAbsErrElevsSoFar = np.mean(np.abs(errorsPosePred[1][:test_i+1]))

        medianAbsErrAzsSoFar = np.median(np.abs(errorsPosePred[0][:test_i+1]))
        medianAbsErrElevsSoFar = np.median(np.abs(errorsPosePred[1][:test_i+1]))

        meanErrorsLightCoeffsSoFar = np.sqrt(np.mean(np.mean(errorsLightCoeffs,axis=1), axis=0))
        meanErrorsVColorsSoFar = np.sqrt(np.mean(np.mean(errorsVColors,axis=1), axis=0))

        errorsPoseFitted = (np.array([]), np.array([]))
        if optimizationTypeDescr[optimizationType] != 'predict':
            errorsPoseFitted = recognition_models.evaluatePrediction(testAzsRel[:test_i+1], testElevsGT[:test_i+1], fittedAzs, fittedElevs)
            meanAbsErrAzsFitted = np.mean(np.abs(errorsPoseFitted[0]))
            meanAbsErrElevsFitted = np.mean(np.abs(errorsPoseFitted[1]))
            medianAbsErrAzsFitted = np.median(np.abs(errorsPoseFitted[0]))
            medianAbsErrElevsFitted = np.median(np.abs(errorsPoseFitted[1]))

        errorsFittedLightCoeffs = np.array([])
        errorsFittedVColors = np.array([])
        if optimizationTypeDescr[optimizationType] != 'predict':
            errorsFittedLightCoeffs = (testLightCoefficientsGTRel[:test_i+1] - fittedRelLightCoeffs)**2
            errorsFittedVColors = (testVColorGT[:test_i+1] - fittedVColors)**2
            meanErrorsFittedLightCoeffs = np.sqrt(np.mean(np.mean(errorsFittedLightCoeffs,axis=1), axis=0))
            meanErrorsFittedVColors =np.sqrt(np.mean(np.mean(errorsFittedVColors,axis=1), axis=0))


        #Write statistics to file.
        with open(resultDir + 'performance.txt', 'w') as expfile:
            # expfile.write(str(z))
            expfile.write("Avg Pred NLL    :" +  str(np.mean(predictedErrorFuns))+ '\n')
            expfile.write("Avg Fitt NLL    :" +  str(np.mean(fittedErrorFuns))+ '\n\n')
            expfile.write("Mean Azimuth Error (predicted) " +  str(meanAbsErrAzs) + '\n')
            expfile.write("Mean Elevation Error (predicted) " +  str(meanAbsErrElevs)+ '\n')
            expfile.write("Median Azimuth Error (predicted) " +  str(medianAbsErrAzs) + '\n')
            expfile.write("Median Elevation Error (predicted) " +  str(medianAbsErrElevs)+ '\n\n')

            expfile.write("Mean Azimuth Error (pred so far) " +  str(meanAbsErrAzsSoFar) + '\n')
            expfile.write("Mean Elevation Error (pred so far) " +  str(meanAbsErrElevsSoFar)+ '\n')
            expfile.write("Median Azimuth Error (pred so far) " +  str(medianAbsErrAzsSoFar) + '\n')
            expfile.write("Median Elevation Error (pred so far) " +  str(medianAbsErrElevsSoFar)+ '\n')
            expfile.write("Mean SH Components Error (pred so far) " +  str(meanErrorsLightCoeffsSoFar)+ '\n')
            expfile.write("Mean Vertex Colors Error (pred so far) " +  str(meanErrorsVColorsSoFar)+ '\n\n')

            if not optimizationTypeDescr[optimizationType] == 'predict':
                expfile.write("Mean Azimuth Error (fitted) " + str(meanAbsErrAzsFitted) + '\n')
                expfile.write("Mean Elevation Error (fitted) " + str(meanAbsErrElevsFitted) + '\n')
                expfile.write("Median Azimuth Error (fitted) " + str(medianAbsErrAzsFitted) + '\n')
                expfile.write("Median Elevation Error (fitted) " + str(medianAbsErrElevsFitted) + '\n')
            expfile.write("Mean SH Components Error (predicted) " +  str(meanErrorsLightCoeffs)+ '\n')
            expfile.write("Mean Vertex Colors Error (predicted) " +  str(meanErrorsVColors)+ '\n')
            if not optimizationTypeDescr[optimizationType] == 'predict':
                expfile.write("Mean SH Components Error (fitted) " +  str(meanErrorsFittedLightCoeffs)+ '\n')
                expfile.write("Mean Vertex Colors Error (fitted) " +  str(meanErrorsFittedVColors)+ '\n')


        if not optimizationTypeDescr[optimizationType] == 'predict':
            headerDesc = "Pred NLL    :" + "Fitt NLL    :" + "Err Pred Az :" + "Err Pred El :" + "Err Fitted Az :" + "Err Fitted El :" + "Occlusions  :"
            perfSamplesData = np.hstack([predictedErrorFuns.reshape([-1,1]), fittedErrorFuns.reshape([-1,1]), errorsPosePred[0][:test_i+1].reshape([-1, 1]), errorsPosePred[1][:test_i+1].reshape([-1, 1]), errorsPoseFitted[0].reshape([-1, 1]), errorsPoseFitted[1].reshape([-1, 1]), testOcclusions[:test_i+1].reshape([-1, 1])])
        elif optimizationTypeDescr[optimizationType] == 'predict' and computePredErrorFuns:
            headerDesc = "Pred NLL    :" + "Err Pred Az :" + "Err Pred El :"  +  "Occlusions  :"
            perfSamplesData = np.hstack([predictedErrorFuns.reshape([-1,1]), errorsPosePred[0][:test_i+1].reshape([-1, 1]), errorsPosePred[1][:test_i+1].reshape([-1, 1]), testOcclusions[:test_i+1].reshape([-1, 1])])
        else:
            headerDesc = "Err Pred Az :" + "Err Pred El :"  +  "Occlusions  :"
            perfSamplesData = np.hstack([errorsPosePred[0][:test_i+1].reshape([-1, 1]), errorsPosePred[1][:test_i+1].reshape([-1, 1]), testOcclusions[:test_i+1].reshape([-1, 1])])

        np.savetxt(resultDir + 'performance_samples.txt', perfSamplesData, delimiter=',', fmt="%g", header=headerDesc)


totalTime = time.time() - startTime
print("Took " + str(totalTime/len(testSet)) + " time per instance.")

errorsPosePred = recognition_models.evaluatePrediction(testAzsRel, testElevsGT, azsPred, elevsPred)

errorsLightCoeffs = (testLightCoefficientsGTRel - relLightCoefficientsGTPred)**2
errorsVColors = (testVColorGT - vColorsPred)**2

meanAbsErrAzs = np.mean(np.abs(errorsPosePred[0]))
meanAbsErrElevs = np.mean(np.abs(errorsPosePred[1]))

medianAbsErrAzs = np.median(np.abs(errorsPosePred[0]))
medianAbsErrElevs = np.median(np.abs(errorsPosePred[1]))

meanErrorsLightCoeffs = np.sqrt(np.mean(np.mean(errorsLightCoeffs,axis=1), axis=0))
meanErrorsVColors = np.sqrt(np.mean(np.mean(errorsVColors,axis=1), axis=0))

errorsPoseFitted = (np.array([]), np.array([]))
errorsPoseFitted = recognition_models.evaluatePrediction(testAzsRel, testElevsGT, fittedAzs, fittedElevs)
if len(azsPredictions) > 0:
    stdevs = np.array([])
    for test_i, test_id in enumerate(testSet):
        stdevs = np.append(stdevs, np.sqrt(-np.log(np.min([np.mean(sinAzsPredSamples[test_i])**2 + np.mean(cosAzsPredSamples[test_i])**2,1]))))

if optimizationTypeDescr[optimizationType] != 'predict':
    fittedVColors = np.vstack(fittedVColors)
    fittedRelLightCoeffs = np.vstack(fittedRelLightCoeffs)
    errorsFittedLightCoeffs = (testLightCoefficientsGTRel - fittedRelLightCoeffs)**2
    errorsFittedVColors = (testVColorGT - fittedVColors)**2


np.savez(resultDir + 'performance_samples.npz', predictedErrorFuns=predictedErrorFuns, fittedErrorFuns= fittedErrorFuns, predErrorAzs=errorsPosePred[0], predErrorElevs=errorsPosePred[1], errorsLightCoeffs=errorsLightCoeffs, errorsVColors=errorsVColors, errorsFittedAzs=errorsPoseFitted[0], errorsFittedElevs=errorsPoseFitted[1], errorsFittedLightCoeffs=errorsFittedLightCoeffs, errorsFittedVColors=errorsFittedVColors, testOcclusions=testOcclusions)
np.savez(resultDir + 'samples.npz', azsPred= azsPred, elevsPred=elevsPred, fittedAzs=fittedAzs, fittedElevs=fittedElevs, vColorsPred=vColorsPred, fittedVColors=fittedVColors, relLightCoefficientsGTPred=relLightCoefficientsGTPred, fittedRelLightCoeffs=fittedRelLightCoeffs )

##Print and plotting results now:

plt.ioff()
import seaborn

if len(stdevs) > 0:

    directory = resultDir + 'nnazsamples_azerror'

    #Show scatter correlations with predicted and azimuth error.
    fig = plt.figure()
    plt.scatter(stdevs*180/np.pi, errorsPosePred[0])
    plt.xlabel('NN Az samples stdev')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,180,-180,180))
    plt.title('Neural net samples Performance scatter plot')
    fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    #Show scatter correlations with occlusions.
    directory = resultDir + 'occlusion_nnazsamplesstdev'
    fig = plt.figure()
    plt.scatter(testOcclusions * 100.0, stdevs*180/np.pi)
    plt.xlabel('Occlusion (%)')
    plt.ylabel('NN Az samples stdev')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,100,0,180))
    plt.title('Occlusion vs az predictions correlations')
    fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    directory = resultDir + 'nnazsamples_vcolorserrors'

    #Show scatter correlations with predicted and azimuth error.
    fig = plt.figure()
    plt.scatter(stdevs*180/np.pi, np.mean(errorsVColors,axis=1))
    plt.xlabel('NN Az samples stdev')
    plt.ylabel('VColor error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,180,-0.0,1))
    plt.title('Neural net samples performance scatter plot')
    fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)


directory = resultDir + 'occlusion_vcolorserrors'
#Show scatter correlations with occlusions.
fig = plt.figure()
plt.scatter(testOcclusions * 100.0, np.mean(errorsVColors,axis=1))
plt.xlabel('Occlusion (%)')
plt.ylabel('Vertex Colors errors')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,100,-0.0,1))
plt.title('Occlusion - vertex color predictions')
fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

directory = resultDir + 'occlusion_vcolorserrors'
#Show scatter correlations with occlusions.
fig = plt.figure()
plt.scatter(testOcclusions * 100.0, np.mean(errorsVColors,axis=1))
plt.xlabel('Occlusion (%)')
plt.ylabel('Vertex Colors errors')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,100,-0.0,1))
plt.title('Occlusion - vertex color fitted predictions')
fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

directory = resultDir + 'occlusion_shcoeffsserrors'
#Show scatter correlations with occlusions.
fig = plt.figure()
plt.scatter(testOcclusions * 100.0, np.mean(errorsLightCoeffs,axis=1))
plt.xlabel('Occlusion (%)')
plt.ylabel('Vertex Colors errors')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,100,-0.0,1))
plt.title('Occlusion - SH coefficients fitted errors')
fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
plt.close(fig)


# Show scatter correlations of occlusion with predicted and fitted color.
if not optimizationTypeDescr[optimizationType] == 'predict':
    directory = resultDir + 'fitted-occlusion_vcolorserrors'
    #Show scatter correlations with occlusions.
    fig = plt.figure()
    plt.scatter(testOcclusions * 100.0, np.mean(errorsVColors,axis=1))
    plt.xlabel('Occlusion (%)')
    plt.ylabel('Vertex Colors errors')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,100,-0.0,1))
    plt.title('Occlusion - vertex color fitted errors')
    fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    directory = resultDir + 'fitted-occlusion_shcoeffsserrors'
    #Show scatter correlations with occlusions.
    fig = plt.figure()
    plt.scatter(testOcclusions * 100.0, np.mean(errorsFittedLightCoeffs,axis=1))
    plt.xlabel('Occlusion (%)')
    plt.ylabel('Fitted SH coefficients errors')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,100,-0.0,1))
    plt.title('Occlusion - SH coefficients fitted errors')
    fig.savefig(directory + '-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

#Show performance averages for different occlusion cut-offs. E.g.

if optimizationTypeDescr[optimizationType] != 'predict':

    meanAbsErrAzsFitted = np.mean(np.abs(errorsPoseFitted[0]))
    meanAbsErrElevsFitted = np.mean(np.abs(errorsPoseFitted[1]))
    medianAbsErrAzsFitted = np.median(np.abs(errorsPoseFitted[0]))
    medianAbsErrElevsFitted = np.median(np.abs(errorsPoseFitted[1]))

if optimizationTypeDescr[optimizationType] != 'predict':
    meanErrorsFittedLightCoeffs = np.sqrt(np.mean(np.mean(errorsFittedLightCoeffs,axis=1), axis=0))
    meanErrorsFittedVColors = np.sqrt(np.mean(np.mean(errorsFittedVColors,axis=1), axis=0))


directory = resultDir + 'predicted-azimuth-error'

fig = plt.figure()
plt.scatter(testElevsGT * 180 / np.pi, errorsPosePred[0])
plt.xlabel('Elevation (degrees)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,90,-90,90))
plt.title('Performance scatter plot')
fig.savefig(directory + '_elev-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.scatter(testOcclusions * 100.0, errorsPosePred[0])
plt.xlabel('Occlusion (%)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,100,-180,180))
plt.title('Performance scatter plot')
fig.savefig(directory + '_occlusion-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.scatter(testAzsRel * 180 / np.pi, errorsPosePred[0])
plt.xlabel('Azimuth (degrees)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,360,-180,180))
plt.title('Performance scatter plot')
fig.savefig(directory  + '_azimuth-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.hist(errorsPosePred[0], bins=18)
plt.xlabel('Angular error')
plt.ylabel('Counts')
x1,x2,y1,y2 = plt.axis()
plt.axis((-180,180,y1, y2))
plt.title('Performance histogram')
fig.savefig(directory  + '_performance-histogram.png', bbox_inches='tight')
plt.close(fig)

directory = resultDir + 'predicted-elevation-error'

fig = plt.figure()
plt.scatter(testElevsGT * 180 / np.pi, errorsPosePred[1])
plt.xlabel('Elevation (degrees)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,90,-90,90))
plt.title('Performance scatter plot')
fig.savefig(directory + '_elev-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.scatter(testOcclusions * 100.0, errorsPosePred[1])
plt.xlabel('Occlusion (%)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,100,-180,180))
plt.title('Performance scatter plot')
fig.savefig(directory + '_occlusion-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.scatter(testAzsRel * 180 / np.pi, errorsPosePred[1])
plt.xlabel('Azimuth (degrees)')
plt.ylabel('Angular error')
x1,x2,y1,y2 = plt.axis()
plt.axis((0,360,-180,180))
plt.title('Performance scatter plot')
fig.savefig(directory  + '_azimuth-performance-scatter.png', bbox_inches='tight')
plt.close(fig)

fig = plt.figure()
plt.hist(errorsPosePred[1], bins=18)
plt.xlabel('Angular error')
plt.ylabel('Counts')
x1,x2,y1,y2 = plt.axis()
plt.axis((-180,180,y1, y2))
plt.title('Performance histogram')
fig.savefig(directory  + '_performance-histogram.png', bbox_inches='tight')
plt.close(fig)

#Fitted predictions plots:

directory = resultDir + 'fitted-azimuth-error'
if not optimizationTypeDescr[optimizationType] == 'predict':
    fig = plt.figure()
    plt.scatter(testElevsGT * 180 / np.pi, errorsPoseFitted[0])
    plt.xlabel('Elevation (degrees)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,90,-90,90))
    plt.title('Performance scatter plot')
    fig.savefig(directory + '_elev-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.scatter(testOcclusions * 100.0, errorsPoseFitted[0])
    plt.xlabel('Occlusion (%)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,100,-180,180))
    plt.title('Performance scatter plot')
    fig.savefig(directory + '_occlusion-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.scatter(testAzsRel * 180 / np.pi, errorsPoseFitted[0])
    plt.xlabel('Azimuth (degrees)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,360,-180,180))
    plt.title('Performance scatter plot')
    fig.savefig(directory  + '_azimuth-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.hist(errorsPoseFitted[0], bins=18)
    plt.xlabel('Angular error')
    plt.ylabel('Counts')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((-180,180,y1, y2))
    plt.title('Performance histogram')
    fig.savefig(directory  + '_performance-histogram.png', bbox_inches='tight')
    plt.close(fig)

    directory = resultDir + 'fitted-elevation-error'

    fig = plt.figure()
    plt.scatter(testElevsGT * 180 / np.pi, errorsPoseFitted[1])
    plt.xlabel('Elevation (degrees)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,90,-90,90))
    plt.title('Performance scatter plot')
    fig.savefig(directory + '_elev-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.scatter(testOcclusions * 100.0, errorsPoseFitted[1])
    plt.xlabel('Occlusion (%)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,100,-180,180))
    plt.title('Performance scatter plot')
    fig.savefig(directory + '_occlusion-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.scatter(testAzsRel * 180 / np.pi, errorsPoseFitted[1])
    plt.xlabel('Azimuth (degrees)')
    plt.ylabel('Angular error')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((0,360,-180,180))
    plt.title('Performance scatter plot')
    fig.savefig(directory  + '_azimuth-performance-scatter.png', bbox_inches='tight')
    plt.close(fig)

    fig = plt.figure()
    plt.hist(errorsPoseFitted[1], bins=18)
    plt.xlabel('Angular error')
    plt.ylabel('Counts')
    x1,x2,y1,y2 = plt.axis()
    plt.axis((-180,180,y1, y2))
    plt.title('Performance histogram')
    fig.savefig(directory  + '_performance-histogram.png', bbox_inches='tight')
    plt.close(fig)

    directory = resultDir + 'fitted-robust-azimuth-error'

plt.ion()

#Write statistics to file.
with open(resultDir + 'performance.txt', 'w') as expfile:
    # expfile.write(str(z))
    expfile.write("Avg Pred NLL    :" +  str(np.mean(predictedErrorFuns))+ '\n')
    expfile.write("Avg Fitt NLL    :" +  str(np.mean(fittedErrorFuns))+ '\n')
    expfile.write("Mean Azimuth Error (predicted) " +  str(meanAbsErrAzs) + '\n')
    expfile.write("Mean Elevation Error (predicted) " +  str(meanAbsErrElevs)+ '\n')
    expfile.write("Median Azimuth Error (predicted) " +  str(medianAbsErrAzs) + '\n')
    expfile.write("Median Elevation Error (predicted) " +  str(medianAbsErrElevs)+ '\n')
    if not optimizationTypeDescr[optimizationType] == 'predict':
        expfile.write("Mean Azimuth Error (fitted) " + str(meanAbsErrAzsFitted) + '\n')
        expfile.write("Mean Elevation Error (fitted) " + str(meanAbsErrElevsFitted) + '\n')
        expfile.write("Median Azimuth Error (fitted) " + str(medianAbsErrAzsFitted) + '\n')
        expfile.write("Median Elevation Error (fitted) " + str(medianAbsErrElevsFitted) + '\n')
    expfile.write("Mean SH Components Error (predicted) " +  str(meanErrorsLightCoeffs)+ '\n')
    expfile.write("Mean Vertex Colors Error (predicted) " +  str(meanErrorsVColors)+ '\n')
    if not optimizationTypeDescr[optimizationType] == 'predict':
        expfile.write("Mean SH Components Error (fitted) " +  str(meanErrorsFittedLightCoeffs)+ '\n')
        expfile.write("Mean Vertex Colors Error (fitted) " +  str(meanErrorsFittedVColors)+ '\n')

if not optimizationTypeDescr[optimizationType] == 'predict':
    headerDesc = "Pred NLL    :" + "Fitt NLL    :" + "Err Pred Az :" + "Err Pred El :" + "Err Fitted Az :" + "Err Fitted El :" + "Occlusions  :"
    perfSamplesData = np.hstack([predictedErrorFuns.reshape([-1,1]), fittedErrorFuns.reshape([-1,1]), errorsPosePred[0].reshape([-1, 1]), errorsPosePred[1].reshape([-1, 1]), errorsPoseFitted[0].reshape([-1, 1]), errorsPoseFitted[1].reshape([-1, 1]), testOcclusions.reshape([-1, 1])])
elif optimizationTypeDescr[optimizationType] == 'predict' and computePredErrorFuns:
    headerDesc = "Pred NLL    :" + "Err Pred Az :" + "Err Pred El :"  +  "Occlusions  :"
    perfSamplesData = np.hstack([predictedErrorFuns.reshape([-1,1]), errorsPosePred[0].reshape([-1, 1]), errorsPosePred[1].reshape([-1, 1]), testOcclusions.reshape([-1, 1])])
else:
    headerDesc = "Err Pred Az :" + "Err Pred El :"  +  "Occlusions  :"
    perfSamplesData = np.hstack([errorsPosePred[0].reshape([-1, 1]), errorsPosePred[1].reshape([-1, 1]), testOcclusions.reshape([-1, 1])])

np.savetxt(resultDir + 'performance_samples.txt', perfSamplesData, delimiter=',', fmt="%g", header=headerDesc)


import tabulate
headers=["Errors", "Pred (mean)", "Fitted (mean)"]


table = [["NLL", np.mean(predictedErrorFuns), 0, np.mean(fittedErrorFuns), 0],
         ["Azimuth", np.mean(np.abs(errorsPosePred[0])), np.mean(np.abs(errorsPoseFitted[0]))],
         ["Elevation", np.mean(np.abs(errorsPosePred[1])), np.mean(np.abs(errorsPoseFitted[1]))],
         ["VColor", meanErrorsVColors, meanErrorsFittedVColors],
         ["SH Light", meanErrorsLightCoeffs, meanErrorsFittedLightCoeffs],
         ]
performanceTable = tabulate.tabulate(table, headers=headers,tablefmt="latex", floatfmt=".2f")
with open(resultDir + 'performance.tex', 'w') as expfile:
    expfile.write(performanceTable)


headers=["Method", "l=0", "SH $l=0,m=-1$", "SH $l=1,m=0$", "SH $l=1,m=1$", "SH $l=1,m=-2$" , "SH $l=2,m=-1$", "SH $l=2,m=0$", "SH $l=2,m=1$", "SH $l=2,m=2$"]


# SMSE_SH_std = np.mean((testLightCoefficientsGTRel - relLightCoefficientsGTPred)**2 + 1e-5, axis=0)/(np.var(testLightCoefficientsGTRel, axis=0) + 1e-5)
# table = [[SHModel, SMSE_SH_std[0], SMSE_SH_std[1], SMSE_SH_std[2],SMSE_SH_std[3], SMSE_SH_std[4], SMSE_SH_std[5],SMSE_SH_std[6], SMSE_SH_std[7], SMSE_SH_std[8] ],
#         ]
# performanceTable = tabulate.tabulate(table, headers=headers,tablefmt="latex", floatfmt=".2f")
# with open(resultDir + 'performance_SH_standardised.tex', 'w') as expfile:
#     expfile.write(performanceTable)

SMSE_SH = np.sqrt(np.mean(errorsLightCoeffs, axis=0))
table = [[SHModel, SMSE_SH[0], SMSE_SH[1], SMSE_SH[2],SMSE_SH[3], SMSE_SH[4], SMSE_SH[5],SMSE_SH[6], SMSE_SH[7], SMSE_SH[8] ],
        ]
performanceTable = tabulate.tabulate(table, headers=headers,tablefmt="latex", floatfmt=".2f")
with open(resultDir + 'performance_SH.tex', 'w') as expfile:
    expfile.write(performanceTable)

# SMSE_SH_std = np.mean((testLightCoefficientsGTRel - fittedRelLightCoeffs)**2 + 1e-5, axis=0)/(np.var(testLightCoefficientsGTRel, axis=0) + 1e-5)
# table = [[SHModel, SMSE_SH_std[0], SMSE_SH_std[1], SMSE_SH_std[2],SMSE_SH_std[3], SMSE_SH_std[4], SMSE_SH_std[5],SMSE_SH_std[6], SMSE_SH_std[7], SMSE_SH_std[8] ],
#         ]
# performanceTable = tabulate.tabulate(table, headers=headers,tablefmt="latex", floatfmt=".2f")
# with open(resultDir + 'performance_SH_fit_standardised.tex', 'w') as expfile:
#     expfile.write(performanceTable)

SMSE_SH = np.sqrt(np.mean(errorsFittedLightCoeffs, axis=0))
table = [[SHModel, SMSE_SH[0], SMSE_SH[1], SMSE_SH[2],SMSE_SH[3], SMSE_SH[4], SMSE_SH[5],SMSE_SH[6], SMSE_SH[7], SMSE_SH[8] ],
        ]
performanceTable = tabulate.tabulate(table, headers=headers,tablefmt="latex", floatfmt=".2f")
with open(resultDir + 'performance_SH_fit.tex', 'w') as expfile:
    expfile.write(performanceTable)

print("Finished backprojecting and fitting estimates.")
