import cqlat as c

from qlat.field import *

import math

def field_expanded(f, expansion_left, expansion_right):
    geo = f.geo()
    multiplicity = geo.multiplicity()
    geo_e = geo_reform(geo, multiplicity, expansion_left, expansion_right)
    f_e = type(f)(ctype = f.ctype, geo = geo_e)
    f_e @= f
    return f_e

def refresh_expanded(field, comm_plan = None):
    if comm_plan is None:
        return c.refresh_expanded_field(field)
    else:
        return c.refresh_expanded_field(field, comm_plan)

def refresh_expanded_1(field):
    return c.refresh_expanded_1_field(field)

class FieldExpandCommPlan:

    def __init__(self):
        self.cdata = c.mk_field_expand_comm_plan()

    def __del__(self):
        c.free_field_expand_comm_plan(self)

    def __imatmul__(self, v1):
        assert isinstance(v1, FieldExpandCommPlan)
        c.set_field_expand_comm_plan(self, v1)
        return self

    def copy(self, is_copying_data = True):
        x = FieldExpandCommPlan()
        if is_copying_data:
            x @= self
        return x

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo):
        return self.copy()

def make_field_expand_comm_plan(comm_marks):
    # comm_marks is of type Field("int8_t")
    cp = FieldExpandCommPlan()
    c.make_field_expand_comm_plan(cp, comm_marks)
    return cp

def mk_phase_field(geo: Geometry, lmom):
    # lmom is in lattice momentum unit
    # exp(i * 2*pi/L * lmom \cdot xg )
    f = Field("Complex", geo, 1)
    c.set_phase_field(f, lmom)
    return f

class FastFourierTransform:

    def __init__(self, fft_infos, *, is_normalizing = False):
        # fft_infos = [ ( fft_dir, is_forward, ), ... ]
        self.fft_infos = fft_infos
        self.is_normalizing = is_normalizing

    def __mul__(self, field):
        for fft_dir, is_forward in self.fft_infos:
            f = field.copy(False)
            c.fft_dir_complex_field(f, field, fft_dir, is_forward)
            field = f
        if self.is_normalizing and self.fft_infos:
            total_site = field.total_site()
            scale_factor = 1
            for fft_dir, is_forward in self.fft_infos:
                scale_factor *= total_site[fft_dir]
            scale_factor = 1.0 / math.sqrt(scale_factor)
            field *= scale_factor
        return field

def mk_fft(is_forward, *, is_only_spatial = False, is_normalizing = False):
    if is_only_spatial:
        fft_infos = [
                (0, is_forward,),
                (1, is_forward,),
                (2, is_forward,),
                ]
        return FastFourierTransform(fft_infos, is_normalizing = is_normalizing)
    else:
        fft_infos = [
                (0, is_forward,),
                (1, is_forward,),
                (2, is_forward,),
                (3, is_forward,),
                ]
        return FastFourierTransform(fft_infos, is_normalizing = is_normalizing)
