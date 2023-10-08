import ctypes
import sys
import os
flags = sys.getdlopenflags()
sys.setdlopenflags(flags | ctypes.RTLD_GLOBAL)

ctypes.cdll.LoadLibrary(
        os.path.join(
            os.path.dirname(__file__),
            'lib/libqlat-utils.so'))

from .cp import *
from .cpa import *

sys.setdlopenflags(flags)
