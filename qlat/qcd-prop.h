#pragma once

#include <qlat/qcd.h>

QLAT_START_NAMESPACE

inline WilsonMatrix make_wilson_matrix_from_vectors(const std::array<ConstHandle<WilsonVector>,4*NUM_COLOR>& cols)
{
  WilsonMatrix ret;
  for (int i = 0; i < 4*NUM_COLOR; ++i) {
    for (int j = 0; j < 4*NUM_COLOR; ++j) {
      ret(j, i) = cols[i]()(j);
    }
  }
  return ret;
}

inline void set_propagator_from_fermion_fields(Propagator4d& prop, const Array<FermionField4d,4*NUM_COLOR> ffs)
{
  TIMER_VERBOSE("set_propagator_from_fermion_fields");
  const Geometry& geo = ffs[0].geo;
  for (int i = 0; i < 4*NUM_COLOR; ++i) {
    qassert(geo == ffs[i].geo);
  }
  prop.init(geo_reform(geo));
  qassert(prop.geo == geo);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    std::array<ConstHandle<WilsonVector>, 4*NUM_COLOR> cols;
    for (int k = 0; k < 4*NUM_COLOR; ++k) {
      cols[k].init(ffs[k].get_elem(xl));
    }
    prop.get_elem(xl) = make_wilson_matrix_from_vectors(cols);
  }
}

inline void set_wilson_matrix_col_from_vector(WilsonMatrix& wm, const int idx, const WilsonVector& col)
{
  for (int j = 0; j < 4*NUM_COLOR; ++j) {
    wm(j, idx) = col(j);
  }
}

inline void set_propagator_col_from_fermion_field(Propagator4d& prop, const int idx, const FermionField4d& ff)
{
  TIMER("set_propagator_col_from_fermion_field");
  const Geometry& geo = ff.geo;
  qassert(geo == prop.geo);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    set_wilson_matrix_col_from_vector(prop.get_elem(xl), idx, ff.get_elem(xl));
  }
}

inline void set_wilson_vector_from_matrix_col(WilsonVector& col, const WilsonMatrix& wm, const int idx)
{
  for (int j = 0; j < 4*NUM_COLOR; ++j) {
    col(j) = wm(j, idx);
  }
}

inline void set_fermion_field_from_propagator_col(FermionField4d& ff, const Propagator4d& prop, const int idx)
{
  TIMER("set_fermion_field_from_propagator_col");
  const Geometry& geo = prop.geo;
  ff.init(geo_reform(geo));
  qassert(geo == ff.geo);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    set_wilson_vector_from_matrix_col(ff.get_elem(xl), prop.get_elem(xl), idx);
  }
}

inline void fermion_field_5d_from_4d(FermionField5d& ff5d, const FermionField4d& ff4d, const int upper, const int lower)
  // ff5d need to be initialized
  // upper componets are right handed
  // lower componets are left handed
{
  TIMER("fermion_field_5d_from_4d");
  const Geometry& geo = ff5d.geo;
  set_zero(ff5d);
  const int sizewvh = sizeof(WilsonVector) / 2;
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    Coordinate x = geo.coordinate_from_index(index);
    memcpy((char*)&(ff5d.get_elem(x, upper)),
        (const char*)&(ff4d.get_elem(x)),
        sizewvh);
    memcpy((char*)&(ff5d.get_elem(x, lower)) + sizewvh,
        (const char*)&(ff4d.get_elem(x)) + sizewvh,
        sizewvh);
  }
}

inline void fermion_field_4d_from_5d(FermionField4d& ff4d, const FermionField5d& ff5d, const int upper, const int lower)
  // upper componets are right handed
  // lower componets are left handed
{
  TIMER("fermion_field_4d_from_5d");
  const Geometry& geo = ff5d.geo;
  ff4d.init(geo_reform(geo));
  set_zero(ff4d);
  const int sizewvh = sizeof(WilsonVector) / 2;
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    Coordinate x = geo.coordinate_from_index(index);
    memcpy((char*)&(ff4d.get_elem(x)),
        (const char*)&(ff5d.get_elem(x, upper)),
        sizewvh);
    memcpy((char*)&(ff4d.get_elem(x)) + sizewvh,
        (const char*)&(ff5d.get_elem(x, lower)) + sizewvh,
        sizewvh);
  }
}

template <class Inverter>
inline void inverse_dwf(FermionField4d& sol, const FermionField4d& src, const Inverter& inv)
  // sol do not need to be initialized
  // inv.geo must be the geometry of the fermion field
  // inverse(sol5d, src5d, inv) perform the inversion
{
  TIMER_VERBOSE("inverse_dwf(4d,4d,inv)");
  const Geometry& geo = src.geo;
  qassert(check_matching_geo(geo, inv.geo));
  sol.init(geo);
  const Geometry geo_ls = geo_reform(inv.geo, inv.fa.ls, 0);
  const int ls = geo_ls.multiplicity;
  FermionField5d sol5d, src5d;
  sol5d.init(geo_ls);
  src5d.init(geo_ls);
  fermion_field_5d_from_4d(src5d, src, 0, ls-1);
  fermion_field_5d_from_4d(sol5d, sol, ls-1, 0);
  inverse(sol5d, src5d, inv);
  fermion_field_4d_from_5d(sol, sol5d, ls-1, 0);
}

template <class Inverter>
inline void inverse(Propagator4d& sol, const Propagator4d& src, const Inverter& inv)
  // sol do not need to be initialized
  // inv.geo must be the geometry of the fermion field
  // inverse(4d, 4d, inv) perform the inversion
{
  TIMER_VERBOSE("inverse(p4d,p4d,inv)");
  const Geometry geo = geo_reform(src.geo);
  sol.init(geo);
  FermionField4d ff_sol, ff_src;
  for (int j = 0; j < 4*NUM_COLOR; ++j) {
    set_fermion_field_from_propagator_col(ff_src, src, j);
    inverse(ff_sol, ff_src, inv);
    set_propagator_col_from_fermion_field(sol, j, ff_sol);
  }
}

inline void smear_propagator(Propagator4d& prop, const GaugeField& gf1,
    const double coef, const int step, const CoordinateD& mom = CoordinateD(), const bool smear_in_time_dir = false)
  // gf1 is left_expanded and refreshed
  // prop is of normal size
{
  TIMER_VERBOSE("smear_propagator");
  if (0 == step) {
    return;
  }
  const Geometry& geo = prop.geo;
  const Geometry geo1 = smear_in_time_dir
    ? geo_resize(geo, 1)
    : geo_resize(geo, Coordinate(1,1,1,0), Coordinate(1,1,1,0));
  const int n_avg = smear_in_time_dir ? 8 : 6;
  const int dir_limit = smear_in_time_dir ? 4 : 3;
  std::array<Complex,8> mom_factors;
  for (int i = 0; i < 8; ++i) {
    const int dir = i - 4;
    const double phase = dir >= 0 ? mom[dir] : -mom[-dir-1];
    mom_factors[i] = std::polar(coef/n_avg, -phase);
  }
  Propagator4d prop1;
  prop1.init(geo1);
  for (int i = 0; i < step; ++i) {
    prop1 = prop;
    refresh_expanded_1(prop1);
#pragma omp parallel for
    for (long index = 0; index < geo.local_volume(); ++index) {
      const Coordinate xl = geo.coordinate_from_index(index);
      WilsonMatrix& wm = prop.get_elem(xl);
      wm *= 1-coef;
      for (int dir = -dir_limit; dir < dir_limit; ++dir) {
        const Coordinate xl1 = coordinate_shifts(xl, dir);
        const ColorMatrix link = dir >= 0
          ? gf1.get_elem(xl, dir)
          : (ColorMatrix)matrix_adjoint(gf1.get_elem(coordinate_shifts(xl, dir), -dir-1));
        wm += mom_factors[dir+4] * link * prop1.get_elem(xl1);
      }
    }
  }
}

inline void set_point_src_fermion_field(FermionField4d& ff, const Coordinate& xg, const int cs, const Complex& value = 1.0)
  // ff need to be initialized
{
  TIMER("set_point_src_fermion_field");
  const Geometry& geo = ff.geo;
  set_zero(ff);
  const Coordinate xl = geo.coordinate_l_from_g(xg);
  if (geo.is_local(xl)) {
    ff.get_elem(xl)(cs) = value;
  }
}

inline void set_point_src(Propagator4d& prop, const Geometry& geo_input, const Coordinate& xg, const Complex& value = 1.0)
{
  TIMER_VERBOSE("set_point_src");
  const Geometry geo = geo_reform(geo_input);
  prop.init(geo);
  FermionField4d src;
  src.init(geo);
  for (int cs = 0; cs < 4 * NUM_COLOR; ++cs) {
    set_point_src_fermion_field(src, xg, cs, value);
    set_propagator_col_from_fermion_field(prop, cs, src);
  }
}

template <class Inverter>
inline void set_point_src_propagator(Propagator4d& prop, const Inverter& inv, const Coordinate& xg, const Complex& value = 1.0)
{
  TIMER_VERBOSE("set_point_src_propagator");
  const Geometry geo = geo_reform(inv.geo);
  prop.init(geo);
  FermionField4d sol, src;
  sol.init(geo);
  src.init(geo);
  for (int cs = 0; cs < 4 * NUM_COLOR; ++cs) {
    set_point_src_fermion_field(src, xg, cs, value);
    set_zero(sol);
    inverse(sol, src, inv);
    set_propagator_col_from_fermion_field(prop, cs, sol);
  }
}

inline CoordinateD lattice_mom_mult(const Coordinate& total_site)
{
  return 2*PI / CoordinateD(total_site);
}

inline CoordinateD lattice_mom_mult(const Geometry& geo)
{
  return lattice_mom_mult(geo.total_site());
}

inline void set_wall_src_fermion_field(FermionField4d& ff, const int tslice, const CoordinateD& lmom, const int cs)
  // ff need to be initialized beforehand
{
  qassert(lmom[3] == 0);
  const Geometry& geo = ff.geo;
  const CoordinateD mom = lmom * lattice_mom_mult(geo);
  set_zero(ff);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Coordinate xg = geo.coordinate_g_from_l(xl);
    if (xg[3] == tslice) {
      double phase = 0.0;
      for (int i = 0; i < DIMN; ++i) {
        phase += mom[i] * xg[i];
      }
      ff.get_elem(xl)(cs) = std::polar(1.0, phase);
    }
  }
}

inline void set_wall_src(Propagator4d& prop, const Geometry& geo_input,
    const int tslice, const CoordinateD& lmom = CoordinateD())
{
  TIMER_VERBOSE("set_wall_src");
  const Geometry geo = geo_reform(geo_input);
  prop.init(geo);
  FermionField4d src;
  src.init(geo);
  for (int cs = 0; cs < 4 * NUM_COLOR; ++cs) {
    set_wall_src_fermion_field(src, tslice, lmom, cs);
    set_propagator_col_from_fermion_field(prop, cs, src);
  }
}

template <class Inverter>
inline void set_wall_src_propagator(Propagator4d& prop, const Inverter& inv,
    const int tslice, const CoordinateD& lmom = CoordinateD())
{
  TIMER_VERBOSE("set_wall_src_propagator");
  const Geometry geo = geo_reform(inv.geo);
  prop.init(geo);
  FermionField4d sol, src;
  sol.init(geo);
  src.init(geo);
  for (int cs = 0; cs < 4 * NUM_COLOR; ++cs) {
    set_wall_src_fermion_field(src, tslice, lmom, cs);
    set_zero(sol);
    inverse(sol, src, inv);
    set_propagator_col_from_fermion_field(prop, cs, sol);
  }
}

inline void set_mom_src_fermion_field(FermionField4d& ff, const CoordinateD& lmom, const int cs)
  // ff need to be initialized beforehand
{
  const Geometry& geo = ff.geo;
  const CoordinateD mom = lmom * lattice_mom_mult(geo);
  set_zero(ff);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Coordinate xg = geo.coordinate_g_from_l(xl);
    double phase = 0.0;
    for (int i = 0; i < DIMN; ++i) {
      phase += mom[i] * xg[i];
    }
    ff.get_elem(xl)(cs) = std::polar(1.0, phase);
  }
}

inline void set_mom_src(Propagator4d& prop, const Geometry& geo_input, const CoordinateD& lmom)
{
  TIMER_VERBOSE("set_mom_src");
  const Geometry& geo = geo_reform(geo_input);
  prop.init(geo);
  qassert(prop.geo == geo);
  FermionField4d src;
  src.init(geo);
  for (int cs = 0; cs < 4*NUM_COLOR; ++cs) {
    set_mom_src_fermion_field(src, lmom, cs);
    set_propagator_col_from_fermion_field(prop, cs, src);
  }
}

template <class Inverter>
inline void set_mom_src_propagator(Propagator4d& prop, Inverter& inv, const CoordinateD& lmom)
{
  TIMER_VERBOSE("set_mom_src_propagator");
  const Geometry& geo = geo_remult(inv.geo);
  prop.init(geo);
  qassert(prop.geo == geo);
  FermionField4d src, sol;
  src.init(geo);
  sol.init(geo);
  for (int cs = 0; cs < 4*NUM_COLOR; ++cs) {
    set_mom_src_fermion_field(src, lmom, cs);
    set_zero(sol);
    inverse(sol, src, inv);
    set_propagator_col_from_fermion_field(prop, cs, sol);
  }
}

// -------------------------------------------------------------------------

inline void set_tslice_mom_src_fermion_field(FermionField4d& ff, const int tslice, const CoordinateD& lmom, const int cs)
  // ff need to be initialized beforehand
{
  qassert(lmom[3] == 0);
  const Geometry& geo = ff.geo;
  const CoordinateD mom = lmom * lattice_mom_mult(geo);
  set_zero(ff);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Coordinate xg = geo.coordinate_g_from_l(xl);
    if (xg[3] == tslice) {
      double phase = 0.0;
      for (int i = 0; i < DIMN; ++i) {
        phase += mom[i] * xg[i];
      }
      ff.get_elem(xl)(cs) = std::polar(1.0, phase);
    }
  }
}

inline void set_tslice_mom_src(Propagator4d& prop, const Geometry& geo_input, const int tslice, const CoordinateD& lmom)
{
  TIMER_VERBOSE("set_tslice_mom_src");
  const Geometry geo = geo_reform(geo_input);
  prop.init(geo);
  FermionField4d src;
  src.init(geo);
  for (int cs = 0; cs < 4 * NUM_COLOR; ++cs) {
    set_tslice_mom_src_fermion_field(src, tslice, lmom, cs);
    set_propagator_col_from_fermion_field(prop, cs, src);
  }
}

template <class Inverter>
inline void set_tslice_mom_src_propagator(Propagator4d& prop, const int tslice, const CoordinateD& lmom, Inverter& inverter)
{
  TIMER_VERBOSE("set_tslice_mom_src_propagator");
  const Geometry& geo = geo_remult(inverter.geo);
  prop.init(geo);
  qassert(prop.geo == geo);
  FermionField4d src, sol;
  src.init(geo);
  sol.init(geo);
  for (int cs = 0; cs < 4*NUM_COLOR; ++cs) {
    set_tslice_mom_src_fermion_field(src, tslice, lmom, cs);
    set_zero(sol);
    inverse(sol, src, inverter);
    set_propagator_col_from_fermion_field(prop, cs, sol);
  }
}

QLAT_END_NAMESPACE