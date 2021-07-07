#!/usr/bin/env bash

if [[ ! -z "$VIRTUAL_ENV" ]]; then
  echo "'deactivate' before running this script."
  exit 1
fi

mkdir .lsp_symlink
cd .lsp_symlink
ln -s /home home
cd ..

rm -rf .venv
virtualenv -p python3.9 .venv

source ./.venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

pip3 install -U torch==1.9.0+cu111 torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html
# pip install -U tensorboard

# Commonly used for dev
pip install -U pynvim
pip install -U 'python-lsp-server[all]'
pip install -U autopep8 flake8 isort pylint yapf pydocstyle black
pip install -U jupyter jupyter_nbextensions_configurator ipyparallel
