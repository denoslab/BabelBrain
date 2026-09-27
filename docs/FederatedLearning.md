# Federated learning in BabelBrain

> DRAFT for review. The feature is in development and not in a BabelBrain release yet.

BabelBrain labs can improve a fast neural-network model of transcranial
ultrasound together, without sharing data. Each lab keeps its training samples
on its own computers; a separate federated learning client trains on them and
shares only model updates. The privacy policy, section "Optional federated
learning", describes exactly what is saved and what is shared.

## Turning it on

Open **Advanced Options → Federated Learning** and choose a level:

- **Off**, the default: nothing is saved.
- **Collect samples locally**: after each successful Step 2 run that qualifies,
  BabelBrain saves one sample in the sample store folder.
- **Collect samples and take part in training**: also lets the federated
  learning client, installed and enrolled separately, train on the samples.

Choose the **Sample store** folder, or leave it empty for
`BabelBrainFL/samples` in your home folder. Saving a sample happens in the
background after Step 2 and never slows down or stops a simulation.

## Which runs become samples

A run is saved only if all of these hold:

- Step 2 finished without error;
- it was planned with a real CT, not ZTE, PETRA, density or no CT;
- the frequency is within 2% of 250, 500 or 750 kHz;
- the transducer is one the model supports, at first the single-element transducer;
- BabelBrain is version 0.8.1 or 0.8.2;
- the physics options in Advanced Options are at their defaults;
- the model's crop around the beam fits inside the simulation domain.

The **Federated Learning** tab shows how many samples are stored per frequency,
the disk space they use, and how many runs were not saved, by reason.

## Reviewing and deleting samples

The tab lists every sample by its random ID, frequency, local split and month.
Select samples and press **Delete selected samples** to remove them from your
computer. The federated learning client stops using a deleted sample at once.

## Adding past runs

Runs done before turning the feature on can be added with the backfill tool.
From the `BabelBrain/BabelBrain` folder:

```bash
python -m FederatedLearning.backfill <folder with past runs> --dry-run \
    --babelbrain-version 0.8.1 --real-ct --default-options
```

BabelBrain does not record the version, the CT type or the physics options with
each run, so you state them for the whole folder; runs without them are skipped.
`--dry-run` only counts; run again without it to save the samples. Running it
twice adds nothing new.

`--eval-regions` is only for the NeuroFUS evaluation set. It labels each sample
with the region of its target, such as P7, so the evaluation can report results
per region. Do not use it for your own sample folder.

## Without the settings tab

Before the tab is available in a build, the level and folder can be set with
environment variables: `BABELBRAIN_FL_LEVEL` to 0, 1 or 2, and
`BABELBRAIN_FL_STORE` to a folder.
