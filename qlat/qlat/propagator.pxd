from . cimport everything as cqlat
from .field_types cimport FieldWilsonMatrix, FieldWilsonVector
from .selected_field_types cimport SelectedFieldWilsonMatrix
from .selected_points_types cimport SelectedPointsWilsonMatrix

cdef class Prop(FieldWilsonMatrix):

    cdef cqlat.Handle[cqlat.Prop] xxx(self)

cdef class SelProp(SelectedFieldWilsonMatrix):

    pass

cdef class PselProp(SelectedPointsWilsonMatrix):

    pass

cdef class FermionField4d(FieldWilsonVector):

    pass
