# Zone-kubelfow-containers  <!-- omit in toc -->

Container images to be used with [The Zone](https://zone.statcan.ca).
User documentation can be found at https://zone.pages.cloud.statcan.ca/docs/en/

## Table of Contents <!-- omit in toc -->
- [Introduction](#introduction)
- [List of maintained images in this github repository](#list-of-maintained-images-in-this-github-repository)
- [Usage](#usage)
  - [Building and Tagging Docker Images](#building-and-tagging-docker-images)
  - [Pulling and Pushing Docker Images](#pulling-and-pushing-docker-images)
  - [Testing Images](#testing-images)
    - [Running and Connecting to Images Locally/Interactively](#running-and-connecting-to-images-locallyinteractively)
    - [Automated Testing](#automated-testing)
- [General Development Workflow](#general-development-workflow)
  - [Running A Zone Container Locally](#running-a-zone-container-locally)
  - [Testing localy](#testing-localy)
  - [Testing On-Platform](#testing-on-platform)
  - [Overview of Images](#overview-of-images)
  - [Adding new software](#adding-new-software)
  - [Adding new Images](#adding-new-images)
  - [Modifying and Testing CI](#modifying-and-testing-ci)
- [Other Development Notes](#other-development-notes)
  - [Github CI](#github-ci)
  - [The `v2` and `latest` tags for the master branch](#the-v2-and-latest-tags-for-the-master-branch)
  - [Set User File Permissions](#set-user-file-permissions)
  - [Troubleshooting](#troubleshooting)
- [Structure](#structure)

## Introduction

Our Container images are based on the community driven [jupyter/docker-stacks](https://github.com/jupyter/docker-stacks).
We chose those images because they are continuously updated and install the most common utilities.
This enables us to focus only on the additional toolsets that we require to enable our data scientists.
These customized images are maintained by the Zone team and are the default images available on The Zone.

## List of maintained images in this github repository

| Image Name     | Notes                                                   | Installations    |
| -------------- | ------------------------------------------------------- | ---------------- |
| jupyterlab-cpu | The base experience. A jupyterlab notebook with various | VsCode, R, Julia |
| sas            | Similar to our jupyterlab-cpu image, except with SAS    |                  |

## Usage

### Building and Tagging Docker Images

Use `make build/IMAGENAME` to build a `Dockerfile`.
This by default generates images with:
* `repo=k8scc01covidacr.azurecr.io`
* `tag=BRANCH_NAME`
For example: `k8scc01covidacr.azurecr.io/IMAGENAME:BRANCH_NAME`.  

`make build` also accepts arguments for REPO and TAG to override these behaviours.
For example, `make build/jupyterlab-cpu REPO=myrepo TAG=notLatest`.

`make post-build/IMAGENAME` is meant for anything that is commonly done after building an image,
but currently only adds common tags.
It adds tags of SHA, SHORT_SHA, and BRANCH_NAME to the given image,
and accepts a `SOURCE_FULL_IMAGE_NAME` argument if you're trying to tag an existing image that has a non-typical name.
For example:

* `make post-build/IMAGENAME` will apply SHA, SHORT_SHA, and BRANCH_NAME tags to `k8scc01covidacr.azurecr.io/IMAGENAME:BRANCH_NAME`
(eg: using the default REPO and TAG names)
* `make post-build/IMAGENAME SOURCE_FULL_IMAGE_NAME=oldRepo/oldImage:oldTag REPO=newRepo`
will make the following new aliases for `oldRepo/oldImage:oldTag REPO=newRepo`:
  * `newRepo/IMAGENAME:SHA`
  * `newRepo/IMAGENAME:SHORT_SHA`
  * `newRepo/IMAGENAME:BRANCH_NAME`

### Pulling and Pushing Docker Images

`make pull/IMAGENAME` and `make push/IMAGENAME` work similarly to `make build/IMAGENAME`.
They either push a local image to the acr, or pull an exisitng one from acr to local.
`REPO` and `TAG` arguments are available to override their default values.

**Note:** To use `make pull` or `make push`, 
you must first log in to ACR (`az acr login -n k8scc01covidacr`)

**Note:** `make push` by default does `docker push --all-tags` in order to push the SHA, SHORT_SHA, etc., tags.  

### Testing Images

#### Running and Connecting to Images Locally/Interactively

To test an image interactively, use `make dev/IMAGENAME`.
This calls `docker run` on a built image,
automatically forwarding ports to your local machine and providing a link to connect to.
Once the docker container is running, it will serve a localhost url to connect to the notebook.

#### Automated Testing

Automated tests are included for the generated Docker images using `pytest`.
This testing suite is modified from the [docker-stacks](https://github.com/jupyter/docker-stacks) test suite.
Image testing is invoked through `make test/IMAGENAME`
(with optional `REPO` and `TAG` arguments like `make build`).

Testing of a given image consists of general and image-specific tests:

```
└── tests
    ├── general                             # General tests applied to all images
    │   └── some_general_test.py
    └── jupyterlab-cpu                      # Test applied to a specific image
        └── some_jupyterlab-cpu-specific_test.py
```

Where `tests/general` tests are applied to all images,
and `tests/IMAGENAME` are applied only to a specific image.
Pytest will start the image locally and then run the provided tests to determine if Jupyterlab is running, python packages are working properly, etc.
Tests are formatted using typical pytest formats
(python files with `def test_SOMETHING()` functions).
`conftest.py` defines some standard scaffolding for image management, etc.

---

## General Development Workflow

### Running A Zone Container Locally

1. Clone the repository with `git clone https://github.com/StatCan/zone-kubeflow-containers`.
2. Run `make install-python-dev-venv` to build a development Python virtual environment.
2.5 Add back from statements in Dockerfiles.
3. Build your image using `make build/IMAGENAME DIRECTORY=STAGENAME`,
e.g. run `make build/base DIRECTORY=base`.
4. Test your image using automated tests through `make test/IMAGENAME`,
e.g. run `make test/sas`.
Remember that tests are designed for the final stage of a build.
5. View your images with `docker images`.
You should see a table printed in the console with your images.
For example you may see:

```
username@hostname:~$ docker images
REPOSITORY                                  TAG        IMAGE ID       CREATED          SIZE
k8scc01covidacr.azurecr.io/jupyterlab-cpu   v2         13f8dc0e4f7a   26 minutes ago   14.6GB
k8scc01covidacr.azurecr.io/sas              v2         2b9acb795079   19 hours ago     15.5GB
```

7. Run your image with `docker run -p 8888:8888 REPO/IMAGENAME:TAG`, e.g. `docker run -p 8888:8888 k8scc01covidacr.azurecr.io/sas:v2`.
8. Open [http://localhost:8888](http://localhost:8888) or `<ip-address-of-server>:8888`.

### Testing localy

1. Clone the repo
2. (optional) `make pull/IMAGENAME TAG=SOMEEXISTINGTAG` to pull an existing version of the image you are working on
(this could be useful as a build cache to reduce development time below)
3. Edit an image via the [image stages](/images) that are used to create it.
4. Build your edited stages and any dependencies using `make build/IMAGENAME DIRECTORY=STAGENAME`
5. Test your image:
   - using automated tests through `make test/IMAGENAME`
   - manually by `docker run -it -p 8888:8888 REPO/IMAGENAME:TAG`,
     then opening it in [http://localhost:8888](http://localhost:8888)

### Testing On-Platform

GitHub Actions CI is enabled to do building, scanning, automated testing, pushing of our images to ACR.
The workflows will trigger on the following:

- any push to master or beta
- any push to an open PR that edits files in `.github/workflows/` or `/images/`

This allows for easy scanning and automated testing for images.

After the workflow is complete,
the images will be available on artifactory.cloud.statcan.ca/das-aaw-docker.
You can access these images on https://zone.statcan.ca using any of the following:

- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:BRANCH_NAME
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:SHA
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:SHORT_SHA

Pushes to master will also have the following tags:

- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:latest
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:v2

### Overview of Images

Each directory in the images folder makes up one stage of the build process.
They each contain the Dockerfile that directs the build, and all related files.

The relationship between the stages and the final product is as shown below.
![The flowchart showing the stages and their order](./docs/images/image-stages.png)

### Adding new software

Software needs to be added by modifying the relevant image stage,
then following the normal build instructions starting with the Generate Dockerfiles step.

Be selective with software installation as image sizes are already quite big (16Gb plus),
and increasing that size would negatively impact the time it takes up for a workspace server to come up
(as well as first time image pulls to a node).
In such cases it may be more relevant to make an image under [aaw-contrib-containers](https://github.com/StatCan/aaw-contrib-containers) as mentioned earlier.

### Adding new Images


1. Identify where the new stage will be placed in the build order
2. Create a new subdirectory in the `/images/` directory for the stage
3. Add a new job to the `./github/workflows/docker.yaml` for the new stage.
See below for a description of all the fields.
4. If this stage was inserted between two existing stages,
update the parent values of any children of this stage
5. If this stage creates an image that will be deployed to users.
A job must be added to test the image in `./github/workflows/docker.yaml`,
and the image name must be added to the matrix in `./github/workflows/docker-nightly.yaml`
See below for a description of all the fields
6. Update the documentation for the new stage.
This is generally updating `images-stages.png` and `image-stages.drawio` in the `docs/images` folder using draw.io.


yaml to create an image
```yaml
  stage-name:                                                         # The name of the stage, will be shown in the CICD workflow
    needs: [vars, parent]                                             # All stages need vars, any stages with a parent must link their direct parent
    uses: ./.github/workflows/docker-steps.yaml
    with:
      image: "stage-name"                                             # The name of the current stage/image
      directory: "directory-name"                                     # The name of the directory in the /images/ folder. /images/base would be "base"
      base-image: "quay.io/jupyter/datascience-notebook:2024-06-17"   # used if the stage is built from an upsteam image. Omit if stage has a local parent
      parent-image: "parent"                                          # The name of the parent stage/image. Omit if stage uses an upsteam image
      parent-image-is-diff: "${{ needs.parent.outputs.is-diff }}"     # Checks if the parent image had changes. Omit if stage uses an upsteam image
      # The following values are static between differnt stages
      registry-name: "${{ needs.vars.outputs.REGISTRY_NAME }}"
      branch-name: "${{ needs.vars.outputs.branch-name }}"
    secrets:
      REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
      REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
```

yaml to create a test
```yaml
  imagename-test:                                       # The name of the test job, usually  imagename-test
    needs: [vars, imagename]                            # Must contain vars and the image that will be tested
    uses: ./.github/workflows/docker-pull-test.yaml
    with:
      image: "imagename"                                # The name of the image that will be tested
      # The following values are static between differnt tests
      registry-name: "${{ needs.vars.outputs.REGISTRY_NAME }}"
      tag: "${{ needs.vars.outputs.branch-name }}"
    secrets:
      REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
      REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
      CVE_ALLOWLIST: ${{ secrets.CVE_ALLOWLIST}}
```

### Modifying and Testing CI

If making changes to CI that cannot be done on a branch (eg: changes to issue_comment triggers), you can:

1. fork the 'kubeflow-containers' repo
2. Modify the CI with

- REGISTRY: (your own dockerhub repo, eg: "j-smith" (no need for the full url))
- Change
  ```
  - uses: azure/docker-login@v1
    with:
      login-server: ${{ env.REGISTRY_NAME }}.azurecr.io
      username: ${{ secrets.REGISTRY_USERNAME }}
      password: ${{ secrets.REGISTRY_PASSWORD }}
  ```
  to
  ```
  - uses: docker/login-action@v1
    with:
      username: ${{ secrets.REGISTRY_USERNAME }}
      password: ${{ secrets.REGISTRY_PASSWORD }}
  ```

3. In your forked repo, define secrets for REGISTRY_USERNAME and REGISTRY_PASSWORD with your dockerhub credentials (you should use an API token, not your actual dockerhub password)

---

## Other Development Notes

### Github CI

The Github workflow is set up to build the images and their dependant stages.
See below for a flowchart of this build.

The main workflow is `docker.yaml`,
it controls the stage build order, and what triggers the CI.
(Pushes to master, pushes to an open pull-request, and nightly builds)

The building of a stage is controled by `docker-steps.yaml`.
It checks if there are changes to the stage or dependant stages.
Builds a new image if there are changes, 
or pulls a copy of the existing image if not.
Testing will be performed if this is the final stage in the build of an image.

![A flowchart of the Github CI workflow](./docs/images/Workflows.png)

### The `v2` and `latest` tags for the master branch


These tags are intended to be `long-lived` in that they will not change.
Subsequent pushes will clobber the previous `IMAGENAME:v2` image.
This means that `IMAGENAME:v2` will be updated automatically as changes are made,
so updates to the tag are not needed.

A new `v3` tag will be created for adding these breaking changes.

**Note**:
The `latest` tag is shared with [aaw-kubeflow-containers](https://github.com/StatCan/aaw-kubeflow-containers),
So isn't reliable

---
### Set User File Permissions

The Dockerfiles in this repo are intended to construct compute environments for a non-root user **jovyan**
to ensure the end user has the least privileges required for their task,
but installation of some of the software needed by the user must be done as the **root** user.
This means that installation of anything that should be user editable
(eg: `pip` and `conda` installs, additional files in `/home/$NB_USER`, etc.)
will by default be owned by **root** and not modifiable by **jovyan**.
**Therefore we must change the permissions of these files to allow the user specific access for modification.**

For example, most pip install/conda install commands occur as the root user
and result in new files in the $CONDA_DIR directory that will be owned by **root**.
This will cause issues if user **jovyan** tried to update or uninstall these packages
(as they by default will not have permission to change/remove these files).

To fix this issue, end any `RUN` command that edits any user-editable files with:

```
fix-permissions $CONDA_DIR && \
fix-permissions /home/$NB_USER
```

This fix edits the permissions of files in these locations to allow user access.
Note that if these are not applied **in the same layer as when the new files were added**
it will result in a duplication of data in the layer
because the act of changing permissions on a file from a previous layer requires a copy of that file into the current layer.
So something like:

```
RUN add_1GB_file_with_wrong_permissions_to_NB_USER.sh && \
	fix-permissions /home/$NB_USER
```

would add a single layer of about 1GB, whereas

```
RUN add_1GB_file_with_wrong_permissions_to_NB_USER.sh

RUN fix-permissions /home/$NB_USER
```

would add two layers, each about 1GB (2GB total).

### Troubleshooting

If running using a VM and RStudio image was built successfully but is not opening correctly on localhost (error 5000 page),
change your CPU allocation in your Linux VM settings to >= 3.
You can also use your VM's system monitor to examine if all CPUs are 100% being used as your container is running.
If so, increase CPU allocation.
This was tested on Linux Ubuntu 20.04 virtual machine.

## Structure

```
.
├── .github/workflow                        # Github CI. Controls the stage build order
│
├── Makefile                                # Controls the interactions with docker commands
│
├── make_helpers                            # Scripts used by makefile
│   ├── get_branch_name.sh
│   ├── get-nvidia-stuff.sh
│   └── post-build-hook.sh
│
├── images                                  # Dockerfile and required resources for stage builds
│   ├── base                                # Common base of the images
│   ├── cmd                                 # Common stage for finalizing most images
│   ├── jupyterlab                          # Jupyterlab specific Dockerfile
│   ├── mid                                 # Common mid point for all images
│   └── sas                                 # SAS specific Dockerfile
│
├── docs                                    # files/images used in documentation (ex. Readme's)
│
└── tests
    ├── general/                            # General tests applied to all images
    ├── jupyterlab-cpu/                     # Test applied to a specific image
    └── README.md
```
