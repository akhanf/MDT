import glob
import hashlib
import logging
import os
import shutil
from contextlib import contextmanager
from multiprocessing.pool import Pool

import numpy as np
from numpy.lib.format import open_memmap

from mdt.IO import Nifti
from mdt.configuration import gzip_optimization_results, gzip_sampling_results
from mdt.utils import create_roi, roi_index_to_volume_index, load_samples

__author__ = 'Robbert Harms'
__date__ = "2016-07-29"
__maintainer__ = "Robbert Harms"
__email__ = "robbert.harms@maastrichtuniversity.nl"


class ModelProcessingStrategy(object):

    def __init__(self, tmp_dir=None):
        """Model processing strategies define in what parts the model is analyzed.

        This uses the problems_to_analyze attribute of the MOT model builder to select the voxels to process. That
        attribute arranges that only a selection of the problems are analyzed instead of all of them.

        Args:
            tmp_dir (str): The temporary dir for the calculations. If set to None we write the temporary results in the
                results folder of each subject. Else, if set set to a specific path we will store the temporary results
                in a subfolder in the given folder (the subfolder will be a hash of the original folder).
        """
        self._logger = logging.getLogger(__name__)
        self._tmp_dir = tmp_dir

    def set_tmp_dir(self, tmp_dir):
        """Set the temporary directory for the calculations. This overwrites the current value.

        Args:
            tmp_dir (str): The temporary dir for the calculations. If set to None we write the temporary results in the
                results folder of each subject. Else, if set to a specific path we will store the temporary results
                in a subfolder in the given folder (the subfolder will be a hash of the original folder).
        """
        self._tmp_dir = tmp_dir
        return self

    def run(self, model, problem_data, output_path, recalculate, worker_generator):
        """Process the given dataset using the logistics the subclass.

        Subclasses of this base class can implement all kind of logic to divide a large dataset in smaller chunks
        (for example slice by slice) and run the processing on each slice separately and join the results afterwards.

        Args:
             model (AbstractModel): An implementation of an AbstractModel that contains the model we want to optimize.
             problem_data (DMRIProblemData): The problem data object with which the model is initialized before running
             output_path (string): The full path to the folder where to place the output
             recalculate (boolean): If we want to recalculate the results if they are already present.
             worker_generator (ModelProcessingWorkerGenerator): the generator for creating the worker we will use

        Returns:
            dict: the results as a dictionary of roi lists
        """


class SimpleProcessingStrategy(ModelProcessingStrategy):

    def __init__(self, tmp_dir=None, honor_voxels_to_analyze=True):
        """This class is a baseclass for all model slice fitting strategies that fit the data in chunks/parts.

        Args:
            honor_voxels_to_analyze (bool): if set to True, we use the model's voxels_to_analyze setting if set
                instead of fitting all voxels in the mask
        """
        super(SimpleProcessingStrategy, self).__init__(tmp_dir=tmp_dir)
        self._honor_voxels_to_analyze = honor_voxels_to_analyze

    @contextmanager
    def _tmp_storage_dir(self, model_output_path, recalculate):
        """Creates a temporary storage dir for the calculations. Removes the dir after calculations.

        Use this manager as a context for running the calculations.

        Args:
            model_output_path (str): the output path of the final model results. We use this to create the tmp_dir.
             recalculate (boolean): if true and the data exists, we throw everything away to start over.
        """
        tmp_storage_dir = self._get_tmp_results_dir(model_output_path)
        self._prepare_tmp_storage_dir(tmp_storage_dir, recalculate)
        yield tmp_storage_dir
        shutil.rmtree(tmp_storage_dir)

    def _get_tmp_results_dir(self, model_output_path):
        """Get the temporary results dir we need to use for processing.

        If self._tmp_dir is set to a non null value we will use a subdirectory in self._tmp_dir.
        Else, if self._tmp_dir is null, we will use a subdir of the model_output_path.

        Args:
            model_output_path (str): the output path of the final model results.

        Returns:
            str: the path to store the temporary results in
        """
        if self._tmp_dir is None:
            return os.path.join(model_output_path, 'tmp_results')

        self._logger.info('Using user defined path for saving the temporary results: {}.'.format(self._tmp_dir))
        return os.path.join(self._tmp_dir, hashlib.md5(model_output_path.encode('utf-8')).hexdigest())

    @staticmethod
    def _prepare_tmp_storage_dir(tmp_storage_dir, recalculate):
        """Prepare the directory for the temporary storage.

        If recalculate is set to True we will remove the storage dir if it exists. Else if False, we will create the
        dir if it does not exist.

        Args:
            tmp_storage_dir (str): the full path to the chunks directory.
            recalculate (boolean): if true and the data exists, we throw everything away to start over.
        """
        if recalculate:
            if os.path.exists(tmp_storage_dir):
                shutil.rmtree(tmp_storage_dir)

        if not os.path.exists(tmp_storage_dir):
            os.makedirs(tmp_storage_dir)

    @contextmanager
    def _selected_indices(self, model, chunk_indices):
        """Create a context in which problems_to_analyze attribute of the models is set to the selected indices.

        Args:
            model: the model to which to set the problems_to_analyze
            chunk_indices (ndarray): the list of voxel indices we want to use for processing
        """
        old_setting = model.problems_to_analyze
        model.problems_to_analyze = chunk_indices
        yield
        model.problems_to_analyze = old_setting


class ChunksProcessingStrategy(SimpleProcessingStrategy):

    def run(self, model, problem_data, output_path, recalculate, worker_generator):
        """Compute all the slices using the implemented chunks generator"""
        with self._tmp_storage_dir(output_path, recalculate) as tmp_storage_dir:
            voxels_processed = 0

            worker = worker_generator.create_worker(model, problem_data, tmp_storage_dir, self._honor_voxels_to_analyze)

            total_roi_indices = worker.get_voxels_to_compute()

            for chunk_indices in self._chunks_generator(model, problem_data, output_path, worker, total_roi_indices):
                with self._selected_indices(model, chunk_indices):
                    self._run_on_chunk(model, problem_data, tmp_storage_dir, worker, chunk_indices,
                                       total_roi_indices, voxels_processed)

                voxels_processed += len(chunk_indices)

            self._logger.info('Computed all voxels, now creating nifti\'s')
            return_data = worker.combine(output_path)

        return return_data

    def _chunks_generator(self, model, problem_data, output_path, worker, total_roi_indices):
        """Generate the slices/chunks we will use for the fitting.

        Yields:
            ndarray: the roi indices per chunk we want to process
        """
        raise NotImplementedError

    def _run_on_chunk(self, model, problem_data, tmp_storage_dir, worker, voxel_indices,
                      voxels_to_process, voxels_processed):
        """Run the worker on the given chunk."""
        total_nmr_voxels = np.count_nonzero(problem_data.mask)
        total_processed = (total_nmr_voxels - len(voxels_to_process)) + voxels_processed

        self._logger.info('Computations are at {0:.2%}, processing next {1} voxels '
                          '({2} voxels in total, {3} processed).'.
                          format(total_processed / total_nmr_voxels, len(voxel_indices), total_nmr_voxels,
                                 total_processed))

        worker.process(voxel_indices)


class ModelProcessingWorkerCreator(object):

    def create_worker(self, model, problem_data, tmp_storage_dir, honor_voxels_to_analyze):
        """Create and return the worker that the processing strategy will use.

        Args:
            model (DMRISingleModel): the model to process
            problem_data (DMRIProblemData): The problem data object with which the model is initialized before running
            tmp_storage_dir (str): the location for the temporary output files
            honor_voxels_to_analyze (boolean): if we should honor the voxels_to_analyze list in the model if applicable.

        Returns:
            ModelProcessingWorker: the worker the processing strategy will use.
        """


class SimpleModelProcessingWorkerGenerator(ModelProcessingWorkerCreator):

    def __init__(self, callback_function):
        """Create a generator that will instantiate the worker using the given callback function.

        Args:
            callback_function: the callback function we will call when create_worker is called.
        """
        self._callback_function = callback_function

    def create_worker(self, model, problem_data, tmp_storage_dir, honor_voxels_to_analyze):
        return self._callback_function(model, problem_data, tmp_storage_dir, honor_voxels_to_analyze)


class ModelProcessingWorker(object):

    def __init__(self, model, problem_data, tmp_storage_dir, honor_voxels_to_analyze):
        self._write_volumes_gzipped = True
        self._used_mask_name = 'UsedMask'
        self._model = model
        self._problem_data = problem_data
        self._tmp_storage_dir = tmp_storage_dir
        self._honor_voxels_to_analyze = honor_voxels_to_analyze
        self._volume_indices = self._create_roi_to_volume_index_lookup_table()

    def process(self, roi_indices):
        """Process the indicated voxels in the way prescribed by this worker.

        Since the processing strategy can use all voxels to do the analysis in one go, this function
        should return all the output it can, i.e. the same kind of output as from the function 'combine()'.

        Args:
            roi_indices (ndarray): The list of roi indices we want to compute

        Returns:
            the results for this single processing step
        """

    def get_voxels_to_compute(self):
        """Get the ROI indices of the voxels we need to compute.

        This should either return an entire list with all the ROI indices for the given brain mask, or a list
        with the specific roi indices we want the strategy to compute.

        Args:
            model (DMRISingleModel): the model to process
            problem_data (DMRIProblemData): The problem data object with which the model is initialized before running
            tmp_storage_dir (str): the location for the temporary output files
            honor_voxels_to_analyze (boolean): if we should honor the voxels_to_analyze list in the model if applicable.

        Returns:
            ndarray: the list of ROI indices (indexing the current mask) with the voxels we want to compute.
        """
        if self._honor_voxels_to_analyze and self._model.problems_to_analyze:
            roi_list = self._model.problems_to_analyze
        else:
            roi_list = np.arange(0, np.count_nonzero(self._problem_data.mask))

        mask_path = os.path.join(self._tmp_storage_dir, '{}.npy'.format(self._used_mask_name))
        if os.path.exists(mask_path):
            return roi_list[np.logical_not(np.squeeze(create_roi(np.load(mask_path, mmap_mode='r'),
                                                                 self._problem_data.mask)[roi_list]))]

        return roi_list

    def combine(self, output_dir):
        """Combine all the calculated parts.

        Args:
            output_dir (str): the location to store the final (combined) output files

        Returns:
            the processing results for as much as this is applicable
        """

    def _write_volumes(self, roi_indices, results, tmp_dir):
        """Write the result arrays to the temporary storage

        Args:
            results (dict): the dictionary with the results to save
            roi_indices (ndarray): the indices of the voxels we computed
            tmp_dir (str): the directory to save the intermediate results to
        """
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        volume_indices = self._volume_indices[roi_indices, :]

        for param_name, result_array in results.items():
            storage_path = os.path.join(tmp_dir, param_name + '.npy')

            map_4d_dim_len = 1
            if len(result_array.shape) > 1:
                map_4d_dim_len = result_array.shape[1]
            else:
                result_array = np.reshape(result_array, (-1, 1))

            mode = 'w+'
            if os.path.isfile(storage_path):
                mode = 'r+'
            tmp_matrix = open_memmap(storage_path, mode=mode, dtype=result_array.dtype,
                                     shape=self._problem_data.mask.shape[0:3] + (map_4d_dim_len,))
            tmp_matrix[volume_indices[:, 0], volume_indices[:, 1], volume_indices[:, 2]] = result_array

        mask_path = os.path.join(tmp_dir, '{}.npy'.format(self._used_mask_name))
        mode = 'w+'
        if os.path.isfile(mask_path):
            mode = 'r+'
        tmp_mask = open_memmap(mask_path, mode=mode, dtype=np.bool, shape=self._problem_data.mask.shape)
        tmp_mask[volume_indices[:, 0], volume_indices[:, 1], volume_indices[:, 2]] = True

    def _combine_volumes(self, output_dir, chunks_dir, volume_header, maps_subdir=''):
        """Combine volumes found in subdirectories to a final volume.

        Args:
            output_dir (str): the location for the output files
            chunks_dir (str): the directory in which all the chunks are located
            maps_subdir (str): we may have per chunk a subdirectory in which the maps are located. This
                parameter is for that subdir. Example search: <chunks_dir>/<chunk>/<maps_subdir>/*.nii*

        Returns:
            dict: the dictionary with the ROIs for every volume, by parameter name
        """
        map_names = list(map(lambda p: os.path.splitext(os.path.basename(p))[0],
                             glob.glob(os.path.join(chunks_dir, maps_subdir, '*.npy'))))

        basic_info = (chunks_dir, maps_subdir, output_dir, maps_subdir, volume_header, self._write_volumes_gzipped)
        info_list = [(map_name, basic_info) for map_name in map_names]

        pool = Pool()
        pool.map(_combine_volumes_write_out, info_list)

    def _create_roi_to_volume_index_lookup_table(self):
        """Creates and returns a lookup table for roi index -> volume index.

        This will create from the given mask a memory mapped lookup table mapping the ROI indices (single integer)
        to the correct voxel location in 3d. To find a voxel index using the ROI index, just index this lookup
        table using the ROI index as index.

        For example, suppose we have the lookup table:
            0: (0, 0, 0)
            1: (0, 0, 1)
            2: (0, 1, 0)
            ...

        We can get the position of a voxel in the 3d space by indexing this array as:
            lookup_table[roi_index]
        to get the correct 3d location.

        Returns:
            memmap ndarray: the memory mapped array which
        """
        storage_path = self._tmp_storage_dir + '_roi_voxel_lookup_table.npy'
        if os.path.isfile(storage_path):
            os.remove(storage_path)
        np.save(storage_path, np.argwhere(self._problem_data.mask))
        return np.load(storage_path, mmap_mode='r')


def _combine_volumes_write_out(info_pair):
    """Write out the given information to a nifti volume.

    Needs to be used by ModelProcessingWorker._combine_volumes
    """
    map_name, info_list = info_pair
    chunks_dir, maps_subdir, output_dir, maps_subdir, volume_header, write_gzipped = info_list

    data = np.load(os.path.join(chunks_dir, maps_subdir, map_name + '.npy'), mmap_mode='r')
    Nifti.write_volume_maps({map_name: data}, os.path.join(output_dir, maps_subdir), volume_header,
                            gzip=write_gzipped)
    del data


class FittingProcessingWorker(ModelProcessingWorker):

    def __init__(self, optimizer, *args):
        """The processing worker for model fitting.

        Use this if you want to use the model processing strategy to do model fitting.

        Args:
            optimizer: the optimization routine to use
        """
        super(FittingProcessingWorker, self).__init__(*args)
        self._optimizer = optimizer
        self._write_volumes_gzipped = gzip_optimization_results()

    def process(self, roi_indices):
        results, extra_output = self._optimizer.minimize(self._model, full_output=True)
        results.update(extra_output)

        self._write_volumes(roi_indices, results, self._tmp_storage_dir)
        return results

    def combine(self, output_dir):
        self._combine_volumes(output_dir, self._tmp_storage_dir, self._problem_data.volume_header)
        return create_roi(Nifti.read_volume_maps(output_dir), self._problem_data.mask)


class SamplingProcessingWorker(ModelProcessingWorker):

    class SampleChainNotStored(object):
        pass

    def __init__(self, sampler, store_samples=False, *args):
        """The processing worker for model sampling.

        Use this if you want to use the model processing strategy to do model sampling.

        Args:
            sampler (AbstractSampler): the optimization sampler to use
            store_samples (boolean): if set to False we will store none of the samples. Use this
                if you are only interested in the volume maps and not in the entire sample chain.
                If set to True the process and combine function will no longer return any results.
        """
        super(SamplingProcessingWorker, self).__init__(*args)
        self._sampler = sampler
        self._write_volumes_gzipped = gzip_sampling_results()
        self._store_samples = store_samples

    def process(self, roi_indices):
        results, other_output = self._sampler.sample(self._model, full_output=True)

        self._write_volumes(roi_indices, other_output, os.path.join(self._tmp_storage_dir, 'volume_maps'))

        if self._store_samples:
            self._write_sample_results(results, self._problem_data.mask, roi_indices, self._tmp_storage_dir)
            return results

        return SamplingProcessingWorker.SampleChainNotStored()

    def combine(self, output_dir):
        self._combine_volumes(output_dir, self._tmp_storage_dir,
                              self._problem_data.volume_header, maps_subdir='volume_maps')

        if self._store_samples:
            for samples in glob.glob(os.path.join(self._tmp_storage_dir, '*.samples.npy')):
                shutil.move(samples, output_dir)
            return load_samples(output_dir)

        return SamplingProcessingWorker.SampleChainNotStored()

    @staticmethod
    def _write_sample_results(results, full_mask, roi_indices, output_path):
        """Write the sample results to a .npy file.

        If the given sample files do not exists, it will create one with enough storage to hold all the samples
        for the given total_nmr_voxels. On storing it should also be given a list of voxel indices with the indices
        of the voxels that are being stored.

        Args:
            results (dict): the samples to write
            full_mask (ndarray): the complete mask for the entire brain
            roi_indices (ndarray): the roi indices of the voxels we computed
            output_path (str): the path to write the samples in
        """
        total_nmr_voxels = np.count_nonzero(full_mask)

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        for map_name, samples in results.items():
            samples_path = os.path.join(output_path, map_name + '.samples.npy')
            mode = 'w+'
            if os.path.isfile(samples_path):
                mode = 'r+'
            saved = open_memmap(samples_path, mode=mode, dtype=samples.dtype,
                                shape=(total_nmr_voxels, samples.shape[1]))
            saved[roi_indices, :] = samples