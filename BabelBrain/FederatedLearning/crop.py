"""
Crop and resample one Step 2 run into sample arrays, and rule 7: the crop fits.

This must be a torch-free port of Tayeb's preprocessing, so that exported
samples match his training data exactly. It waits for his code and answers,
T3 to T5 in babelbrain-docs/open-questions.md:

- T3: the crop and resampling code itself.
- T4: complex sign convention, normalisation, crop placement along the beam
  relative to the transducer and the focus, and the exact grid shapes.
- T5: which DataForSim arrays give CT, speed of sound, attenuation and the
  brain mask. Candidates are in context/babelbrain-code-notes.md.

Until then ``crop_sample`` raises CropNotAvailable and the exporter records
the run as ``crop_pending``, so nothing half-right is ever written.
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
