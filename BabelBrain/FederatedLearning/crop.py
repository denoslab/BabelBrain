"""
Crop and resample one Step 2 run into sample arrays, and rule 7: the crop fits.

This must be a torch-free port of Tayeb's preprocessing, so that exported
samples match his training data exactly. Answers of 2026-09-27, T3 to T5 in
babelbrain-docs/open-questions.md:

- T3: Tayeb will share his crop and resampling code; port it here.
- T4: the complex sign convention is the paper's, e^(-i omega t) with
  P = P_real - i P_imag; fields are stored raw, in pascals, and the model
  code normalises; the 41.2 x 41.2 x 82.4 mm crop starts at the transducer
  face and runs along the beam; the grids are 84 x 84 x 168, 112 x 112 x 224
  and 168 x 168 x 336 at 250, 500 and 750 kHz.
- T5: CT from MaterialMapCT; speed of sound and attenuation from MaterialMap
  with the Material table; the brain mask from the SimNIBS segmentation,
  which is not in DataForSim.h5, so the run's SimNIBS folder must reach the
  exporter.

Until the port is in, ``crop_sample`` raises CropNotAvailable and the exporter
records the run as ``crop_pending``, so nothing half-right is ever written.
"""

CROP_IMPLEMENTED = False


class CropNotAvailable(Exception):
    """The crop port is not in place yet."""


class CropDoesNotFit(Exception):
    """Rule 7: the crop would reach beyond the simulation domain by more than allowed."""


def crop_sample(full_sol_path, water_sol_path, bucket_hz):
    """
    Return the sample arrays for one run, named and shaped as in schema.SAMPLE_DATASETS.

    Raises CropDoesNotFit for rule 7, and CropNotAvailable until the port exists.
    """
    raise CropNotAvailable('the crop port waits for Tayeb\'s code, T3 to T5')
