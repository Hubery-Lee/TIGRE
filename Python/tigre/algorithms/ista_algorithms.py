from __future__ import division
import numpy as np
import tigre
from tigre.algorithms.iterative_recon_alg import IterativeReconAlg
from tigre.algorithms.iterative_recon_alg import decorator
import time
from tigre.utilities.im_3d_denoise import im3ddenoise
from tigre.algorithms.single_pass_algorithms import FDK
import copy


class FISTA(IterativeReconAlg):
    """
    Solves the reconstruction problem
    using the projection data PROJ taken over ALPHA angles, corresponding
    to the geometry descrived in GEO, using NITER iterations.

    Parameters
    ----------
    :param proj: (np.ndarray, dtype=np.float32)
    Input data, shape = (geo.nDector, nangles)

    :param geo: (tigre.geometry)
    Geometry of detector and image (see examples/Demo code)

    :param angles: (np.ndarray , dtype=np.float32)
    angles of projection, shape = (nangles,3)

    :param niter: (int)
    number of iterations for reconstruction algorithm

    :param kwargs: (dict)
    optional parameters

    Keyword Arguments
    -----------------
    :keyword hyper: (np.float64)
        hyper parameter proportional to the largest eigenvalue of the
        matrix A in the equations Ax-b and ATb.
        Empirical tests show, for the headphantom object:

        nVoxel = np.array([64,64,64]),      hyper (approx=) 2.e8
        nVoxel = np.array([512,512,512]),   hyper (approx=) 2.e4

    :keyword init: (str)
        Describes different initialization techniques.
              "none"     : Initializes the image to zeros (default)
              "FDK"      : intializes image to FDK reconstrucition
              "multigrid": Initializes image by solving the problem in
                           small scale and increasing it when relative
                           convergence is reached.
              "image"    : Initialization using a user specified
                           image. Not recommended unless you really
                           know what you are doing.

    :keyword InitImg: (np.ndarray)
        Not yet implemented. Image for the "image" initialization.

    :keyword verbose:  (Boolean)
        Feedback print statements for algorithm progress
        default=True

    :keyword Quameasopts: (list)
        Asks the algorithm for a set of quality measurement
        parameters. Input should contain a list or tuple of strings of
        quality measurement names. Examples:
            RMSE, CC, UQI, MSSIM

    :keyword OrderStrategy : (str)
        Chooses the subset ordering strategy. Options are:
                 "ordered"        : uses them in the input order, but
                                    divided
                 "random"         : orders them randomply
                 "angularDistance": chooses the next subset with the
                                    biggest angular distance with the
                                    ones used
    :keyword tviter: (int)
        Number of iterations of im3ddenoise for every iteration.
        Default: 20

    :keyword lambda: (float)
        Adjustement of lambdaForTV. Default: 0.1


    Usage
    --------
    >>> import numpy as np
    >>> import tigre
    >>> import tigre.algorithms as algs
    >>> from tigre.demos.Test_data import data_loader
    >>> geo = tigre.geometry(mode='cone',default_geo=True,
    >>>                         nVoxel=np.array([512,512,512]))
    >>> angles = np.linspace(0,2*np.pi,100)
    >>> src_img = data_loader.load_head_phantom(geo.nVoxel)
    >>> proj = tigre.Ax(src_img,geo,angles)
    >>> output = algs.fista(proj,geo,angles,niter=50
    >>>                                 hyper=2.e4)

    tigre.demos.run() to launch ipython notebook file with examples.


    --------------------------------------------------------------------
    This file is part of the TIGRE Toolbox

    Copyright (c) 2015, University of Bath and
                        CERN-European Organization for Nuclear Research
                        All rights reserved.

    License:            Open Source under BSD.
                        See the full license at
                        https://github.com/CERN/TIGRE/license.txt

    Contact:            tigre.toolbox@gmail.com
    Codes:              https://github.com/CERN/TIGRE/
    --------------------------------------------------------------------
    Coded by:          MATLAB (original code): Ander Biguri
                       PYTHON : Reuben Lindroos

     """

    def __init__(self, proj, geo, angles, niter, **kwargs):

        # Dont precompute W and V
        kwargs.update(dict(W=None,
                           V=None,
                           ))
        kwargs.update(dict(blocksize=angles.shape[0]))
        IterativeReconAlg.__init__(self, proj, geo, angles, niter, **kwargs)
        self.lmbda = 0.1
        if 'hyper' not in kwargs:
            self.__L__ = 2.e4
        else:
            self.__L__ = kwargs['hyper']
        if 'tviter' not in kwargs:
            self.__numiter_tv__ = 20
        else:
            self.__numiter_tv__ = kwargs['tviter']
        if 'lambda' not in kwargs:
            self.__lambda__ = 0.1
        else:
            self.__lambda__ = kwargs['lambda']
        self.__t__ = 1
        self.__bm__ = 1. / self.__L__

    # overide update_image from iterative recon alg to remove W.
    def update_image(self, geo, angle, iteration):
        """
        VERBOSE:
         for j in range(angleblocks):
             angle = np.array([alpha[j]], dtype=np.float32)
             proj_err = proj[angle_index[j]] - Ax(res, geo, angle, 'ray-voxel')
             backprj = Atb(proj_err, geo, angle, 'FDK')
             res += backprj
             res[res<0]=0

        :return: None
        """
        self.res += self.__bm__ * 2 * tigre.Atb((self.proj[self.angle_index[iteration]] - tigre.Ax(
            self.res, geo, angle, 'interpolated')), geo, angle, 'matched')

    def run_main_iter(self):
        """
        Goes through the main iteration for the given configuration.
        :return: None
        """
        t = self.__t__
        Quameasopts = self.Quameasopts
        x_rec = copy.deepcopy(self.res)
        lambdaForTv = 2 * self.__bm__ * self.__lambda__
        for i in range(self.niter):

            res_prev = None
            if Quameasopts is not None:
                res_prev = copy.deepcopy(self.res)
            if self.verbose:
                if i == 0:
                    print(str(self.name).upper() +
                          ' ' + "algorithm in progress.")
                    toc = time.clock()
                if i == 1:
                    tic = time.clock()
                    print('Esitmated time until completetion (s): ' +
                          str((self.niter - 1) * (tic - toc)))
            getattr(self, self.dataminimizing)()

            x_rec_old = copy.deepcopy(x_rec)
            x_rec = im3ddenoise(self.res, self.__numiter_tv__, 1. / lambdaForTv)
            t_old = t
            t = (1 + np.sqrt(1 + 4 * t ** 2)) / 2
            self.res = x_rec + (t_old - 1) / t * (x_rec - x_rec_old)

            self.error_measurement(res_prev, i)


fista = decorator(FISTA, name='FISTA')


class ISTA(FISTA):
    __doc__ = FISTA.__doc__

    def __int__(self, proj, geo, angles, niter, **kwargs):
        FISTA.__init__(self, proj, geo, angles, niter, **kwargs)

    def run_main_iter(self):
        """
        Goes through the main iteration for the given configuration.
        :return: None
        """
        Quameasopts = self.Quameasopts
        lambdaForTv = 2 * self.__bm__ * self.lmbda
        for i in range(self.niter):

            res_prev = None
            if Quameasopts is not None:
                res_prev = copy.deepcopy(self.res)
            if self.verbose:
                if i == 0:
                    print(str(self.name).upper() +
                          ' ' + "algorithm in progress.")
                    toc = time.clock()
                if i == 1:
                    tic = time.clock()
                    print('Esitmated time until completetion (s): ' +
                          str((self.niter - 1) * (tic - toc)))
            getattr(self, self.dataminimizing)()

            self.res = im3ddenoise(self.res, 20, 1. / lambdaForTv)

            self.error_measurement(res_prev, i)


ista = decorator(ISTA, name='ISTA')
