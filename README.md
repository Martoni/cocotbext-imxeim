# cocotbext-imxeim
cocotb test module for i.MX EIM and WEIM bus. This module is mainly inspired
from [cocomod-wishbone](https://github.com/wallento/cocomod-wishbone) module.

# Install it

Clone the git, then pip install:
```bash
git clone https://github.com/Martoni/cocotbext-imxeim.git
cd cocotbext-imxeim
python -m pip install -e .
```

# use it in testbench

Import it :
```python
from cocotbext.imxeim.driver import EIMMaster
from cocotbext.imxeim.driver import EIMOp
```

TODO

# Related projects

These projects use cocotbext-imxeim :

- [ChisArmadeus](https://github.com/Martoni/ChisArmadeus): Armadeus imx
	interface wrappers written in Chisel HDL.
