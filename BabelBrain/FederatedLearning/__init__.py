"""
Opt-in federated learning support for BabelBrain.

After a successful Step 2 run, and only when the user has turned FL on,
BabelBrain can save one training sample for the tFUS-FNO surrogate model to
a local sample store. Samples never leave the machine; a separate FL client
trains on them and shares only model weights.

Nothing here may block the GUI or fail a simulation. The package needs only
numpy and h5py, which BabelBrain already ships.
"""

# FL levels, stored like TelemetryLevel. Off is the default.
FL_OFF = 0
FL_COLLECT = 1
FL_TRAIN = 2
FL_LEVELS = (FL_OFF, FL_COLLECT, FL_TRAIN)

# Until the FL settings tab exists, the level and store come from these
LEVEL_ENV = 'BABELBRAIN_FL_LEVEL'
STORE_ENV = 'BABELBRAIN_FL_STORE'
