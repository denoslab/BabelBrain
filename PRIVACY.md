# BabelBrain Privacy Policy

**Effective date:** 2026-06-10.  
**Applies to:** the BabelBrain desktop application (macOS, Windows, Linux) and its installers version 0.8.2 and above.  
**Maintained by:** NeuroFUS laboratory, University of Calgary.  
**Contact:** samuel.pichardo@ucalgary.ca  

BabelBrain is an open-source desktop application for prospective modeling of
transcranial focused ultrasound. This policy explains what information the
application does and does not collect.

## Summary

- BabelBrain runs **locally on your computer**. The medical images, trajectories,
  simulation inputs and results you work with are processed on your machine and
  are **never uploaded to us** or to any third party.
- The application collects **no usage information by default**.
- An **optional, opt-in** telemetry feature lets you voluntarily share a small
  amount of **anonymous** technical information to help the project demonstrate
  real-world use to its academic funding agencies. It is **disabled unless you
  explicitly turn it on**, and you can change or turn it off at any time.

## Information processed locally (never collected by us)

BabelBrain reads and writes medical imaging data (e.g. CT/MRI NIfTI files),
trajectory/transform files, configuration files and simulation outputs. All of
this stays on your device (or on storage you control). We do **not** receive,
transmit, or store:

- patient, subject, or any personal/health information;
- the contents of any file you open, generate, or save;
- file names, file paths, or directory contents;
- your name, email address, or account information;
- your IP address (see "What we do not collect", below).

## Optional telemetry (opt-in)

To help us report real-world usage to academic funders and to understand the
tool's performance across hardware, BabelBrain can optionally send a small amount
of anonymous technical data. This feature is **off by default**. The first time
you run the application you are asked, once, whether you wish to participate, and
you choose one of the following levels. You can review or change your choice at
any time under **Advanced Options → Telemetry**.

| Level | What is shared |
|-------|----------------|
| **L0 — No telemetry (default)** | Nothing is sent. |
| **L1 — Basic** | A signal that the app ran, plus CPU model, operating system, amount of main memory, GPU model, and error reports. |
| **L2** | Everything in L1, plus the execution times of the three main simulation steps. |
| **L3** | Everything in L2, plus the selected ultrasound frequency, points-per-wavelength (PPW), simulation domain size, and granular timings of the most computationally demanding sections. |
| **L4** | Everything in L3, plus the transducer model selected and the total run duration (no further timing detail). |

Each telemetry submission is tagged with a **random install identifier** (a
UUID generated on your machine and stored locally). This identifier lets us avoid
double-counting the same installation; it is **not derived from, and cannot be
tied back to, you or your device's identity**.

### What we do not collect, even with telemetry enabled

- No personal, patient, or health information.
- No file contents, file names, or paths.
- No images, trajectories, or simulation results.
- No IP address. BabelBrain does not collect, transmit, or store your IP address
  as part of telemetry. (As with any internet request, the receiving service
  must momentarily handle the network connection to deliver the data; that
  connection metadata is not part of, or retained in, the telemetry dataset.)

## How telemetry is transmitted and stored

When telemetry is enabled, the selected data is sent over an encrypted (HTTPS)
connection to a data-collection form hosted by **Google (Google Forms)**, which
acts as our data processor for storing the responses. We use the collected,
aggregated data solely to:

- demonstrate adoption and real-world usage to our funding agencies;
- understand and improve the application's performance and reliability.

We do not sell telemetry data, use it for advertising, or attempt to
re-identify contributors. Google's handling of the underlying form
infrastructure is governed by Google's Privacy Policy
(https://policies.google.com/privacy).

## Optional federated learning (opt-in)

> DRAFT for review. This section describes a feature that is in development
> and not yet part of a BabelBrain release.

BabelBrain can optionally help improve a fast neural-network model of
transcranial ultrasound, trained jointly by several BabelBrain labs with
**federated learning**. In federated learning, the training data stays at each
lab; only changes to the model are shared. This feature is **off by default**
and has no first-launch prompt. You can turn it on, change it or turn it off at
any time under **Advanced Options → Federated Learning**.

| Level | What happens |
|-------|--------------|
| **Off (default)** | Nothing is saved and nothing is shared. |
| **Collect samples locally** | After each successful Step 2 run planned with a real CT, BabelBrain saves one training sample in a folder on your computer. Nothing is shared. |
| **Collect and train** | As above, and a separate federated learning client, installed and enrolled by you, trains the model on these samples and shares the results described below. |

### What a training sample holds, and where it stays

A sample is a small crop of the simulation around the ultrasound beam: the CT
values, the simulated pressure fields in water and through the skull, and
speed-of-sound, attenuation and brain-tissue maps on the same grid, plus the
frequency, voxel size, transducer type, BabelBrain version and the month of
export. Samples are saved only in the sample store folder you choose, by
default `BabelBrainFL/samples` in your home folder, and are **never uploaded**.

A sample never holds names, file names or paths, dates other than the month of
export, NIfTI headers or scanner coordinates, subject or target names,
trajectory files, or T1w or T2w MRI images. To keep all targets of one subject
together when the model is checked locally, each sample carries a code derived
from its input folder with a random secret that is created on your computer and
never leaves it; the code cannot be turned back into the folder name.

### What is shared at the "Collect and train" level

The federated learning client sends, over an encrypted connection, to a
coordination server run by the NeuroFUS laboratory at the University of Calgary:

- changes to the model's weights after training on your samples, which do not
  contain the samples;
- the number of samples used, and summary measures of how well the model fits
  them, such as average errors;
- technical information about the training run, such as its duration, memory
  use, device type, and log messages, which contain no file names or paths.

No images, samples, simulation results, file names or personal information are
sent. The client identifies your lab only with a random site identifier and
the access token it receives at enrolment.

### Withdrawing and deleting

- Choose **Off** to stop saving samples. Choosing **Collect samples locally**
  stops any training contribution while keeping your samples.
- The **Federated Learning** tab lists every stored sample; **Delete** removes
  it from your computer. Deleting the sample store folder removes all of them.
- Model updates already combined into a shared model cannot be separated from
  it again. Contact us at the address below to leave the federated network.

## Legal basis and your control

- Participation is **voluntary and consent-based** (opt-in). No telemetry is sent
  unless you select a level above L0.
- You can **change or withdraw** your choice at any time in
  **Advanced Options → Telemetry** by selecting "L0 — No telemetry".
- Because the data is anonymous and tied only to a random install identifier, we
  generally cannot locate or delete an individual past submission. If you have a
  specific concern, contact us at the address above and we will assist where we
  are able.

## Crash and error reports

Error information included in telemetry (L1 and above) consists of technical
diagnostic messages about failures in the application. We make reasonable efforts
to avoid including any personal or file-specific information in these reports.

## Children

BabelBrain is a research tool intended for professional and academic use and is
not directed to children.

## Changes to this policy

We may update this policy as the application evolves (for example, if the
telemetry mechanism or the data categories change). Material changes will be
reflected in this document, with an updated "Effective date." The current version
is always available in the project's source repository.

## Contact

Questions about this policy or about BabelBrain's data practices can be sent to
samuel.pichardo@ucalgary.ca. The project source code is available at
https://github.com/ProteusMRIgHIFU/BabelBrain.
