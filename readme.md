## Install a Hershey Font
### 1. Download
Go to https://gitlab.com/oskay/svg-fonts/-/tree/master/fonts?ref_type=heads and download a .svg font

### 2. Installing
Place .svg font file in directory `fonts/`

## Set up python virtual environment and dependencies
### 1. Create the virtual environment
``` shell
python3 -m venv .venv
```

### 2. Active the environment
MacOS / Linux
``` shell
source .venv/bin/activate
```

Windows (cmd prompt)
``` shell
.venv\Scripts\activate.bat
```

Windows (powershell)
``` shell
.venv\Scripts\Activate.ps1
```

### 3. Install the dependencies
``` shell
pip install -r requirements.txt
```

## Running the typewritter
``` shell
python3 idraw_typewriter_controller.py
```
