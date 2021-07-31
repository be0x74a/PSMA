# PSMA
## Programmable Sandbox for Malware Analysis [Master's Dissertation Project]

PSMA is a scalable dynamic malware analysis system that enables researchers to perform programmable and repeatable experiments.

## Features

- Module-load based behaviour
- VirtualBox-based execution environment
- Celery workers for horizontal scaling
- Versioned storage system for developed modules and virtual machine images
- YAML definition of modules, virtual machine images and experiments
- Docker-Compose deployment of most parts of the system
- Monitoring of the system using Node Exporter, cAdvisor and Celery-Exporter with Grafana Dashboards


## Usage

PSMA requires [Docker](https://docs.docker.com/engine/install/), [Docker-Compose](https://docs.docker.com/compose/install/) and [VirtualBox and its SDK](https://www.python.org/downloads/) to be installed.
Create a virtual environment and install the requirements and VirtualBox SDK.

```shell
python3 -m venv ./.venv
source ./.venv/bin/activate
pip install -r requirements.txt
export VBOX_INSTALL_PATH=/usr/lib/virtualbox
sudo -E ./.venv/bin/python3 <path_for_sdk>/installer/vboxapisetup.py
```

To run the full system run:

```shell
./scripts/full_system_run.sh [RUNTIME_STORAGE_FOLDER]
```

PSMA is now available at [http:localhost:8080/](http:localhost:8080/) and the Grafana service at [http://localhost:9090](http://localhost:9090).