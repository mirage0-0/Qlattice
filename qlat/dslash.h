#pragma once

#include <qlat/qcd.h>
#include <qlat/qcd-utils.h>
#include <qlat/fermion-action.h>

QLAT_START_NAMESPACE

struct InverterParams
{
  double stop_rsd;
  long max_num_iter;
  long max_mixed_precision_cycle;
  //
  void init()
  {
    stop_rsd = 1.0e-8;
    max_num_iter = 50000;
    max_mixed_precision_cycle = 100;
  }
  //
  InverterParams()
  {
    init();
  }
};

struct LowModes
{
  // TODO
};

struct InverterDomainWall
{
  Geometry geo;
  FermionAction fa;
  GaugeField gf;
  InverterParams ip;
  //
  InverterDomainWall()
  {
    init();
  }
  //
  void init()
  {
    ip.init();
  }
  //
  void setup()
  {
    TIMER_VERBOSE("Inv::setup");
  }
  void setup(const GaugeField& gf_, const FermionAction& fa_)
  {
    geo = geo_reform(gf_.geo);
    gf.init();
    set_left_expanded_gauge_field(gf, gf_);
    fa = fa_;
    setup();
  }
  void setup(const GaugeField& gf_, const FermionAction& fa_, const LowModes& lm_)
  {
    setup(gf_, fa_);
    // TODO
  }
  //
  double& stop_rsd()
  {
    return ip.stop_rsd;
  }
  //
  long& max_num_iter()
  {
    return ip.max_num_iter;
  }
  //
  long& max_mixed_precision_cycle()
  {
    return ip.max_mixed_precision_cycle;
  }
};

inline void load_or_compute_low_modes(LowModes& lm, const std::string& path,
    const GaugeField& gf, const FermionAction& fa, const LancArg& la)
{
  TIMER_VERBOSE("load_or_compute_low_modes");
  // TODO
}

inline void setup_inverter(InverterDomainWall& inv)
{
  inv.setup();
}

inline void setup_inverter(InverterDomainWall& inv, const GaugeField& gf, const FermionAction& fa)
{
  inv.setup(gf, fa);
}

inline void setup_inverter(InverterDomainWall& inv, const GaugeField& gf, const FermionAction& fa, const LowModes& lm)
{
  inv.setup(gf, fa, lm);
}

inline void multiply_m_dwf_no_comm(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv)
{
  TIMER("multiply_m_dwf_no_comm(5d,5d,Inv)");
  const Geometry geo = geo_resize(in.geo);
  qassert(is_matching_geo(inv.geo, geo));
  out.init(geo);
  set_zero(out);
  const FermionAction& fa = inv.fa;
  const GaugeField& gf = inv.gf;
  qassert(in.geo.multiplicity == fa.ls);
  qassert(out.geo.multiplicity == fa.ls);
  qassert(fa.mobius_scale == 1.0);
  qassert(fa.bs.size() == fa.ls);
  qassert(fa.cs.size() == fa.ls);
  const std::array<SpinMatrix,4>& gammas = SpinMatrixConstants::get_cps_gammas();
  const SpinMatrix& gamma5 = SpinMatrixConstants::get_gamma5();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  const SpinMatrix p_p = 0.5 * (unit + gamma5);
  const SpinMatrix p_m = 0.5 * (unit - gamma5);
  std::array<SpinMatrix,4> p_mu_p;
  std::array<SpinMatrix,4> p_mu_m;
  for (int mu = 0; mu < 4; ++mu) {
    p_mu_p[mu] = 0.5 * (unit + gammas[mu]);
    p_mu_m[mu] = 0.5 * (unit - gammas[mu]);
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    Vector<WilsonVector> v = out.get_elems(xl);
    {
      const Vector<WilsonVector> iv = in.get_elems_const(xl);
      for (int m = 0; m < fa.ls; ++m) {
        v[m] = (5.0 - fa.m5) * iv[m];
        v[m] -= p_m * (m < fa.ls-1 ? iv[m+1] : (WilsonVector)(-fa.mass * iv[0]));
        v[m] -= p_p * (m > 0 ? iv[m-1] : (WilsonVector)(-fa.mass * iv[fa.ls-1]));
      }
    }
    for (int mu = 0; mu < 4; ++mu) {
      const Coordinate xl_p = coordinate_shifts(xl, mu);
      const Coordinate xl_m = coordinate_shifts(xl, -mu-1);
      const ColorMatrix u_p = gf.get_elem(xl, mu);
      const ColorMatrix u_m = matrix_adjoint(gf.get_elem(xl_m, mu));
      const Vector<WilsonVector> iv_p = in.get_elems_const(xl_p);
      const Vector<WilsonVector> iv_m = in.get_elems_const(xl_m);
      for (int m = 0; m < fa.ls; ++m) {
        v[m] -= u_p * (p_mu_m[mu] * iv_p[m]);
        v[m] -= u_m * (p_mu_p[mu] * iv_m[m]);
      }
    }
  }
}

inline void multiply_m_dwf(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv)
  // out can be the same object as in
{
  TIMER("multiply_m_dwf(5d,5d,Inv)");
  const Geometry geo1 = geo_resize(in.geo, 1);
  FermionField5d in1;
  in1.init(geo1);
  in1 = in;
  refresh_expanded_1(in1);
  multiply_m_dwf_no_comm(out, in1, inv);
}

inline void multiply_wilson_d_no_comm(FermionField5d& out, const FermionField5d& in, const GaugeField& gf, const double mass)
  // set_left_expanded_gauge_field(gf, gf_);
  // in.geo = geo_reform(geo, 1, ls);
  // refresh_expanded_1(in);
{
  TIMER("multiply_wilson_d_no_comm(5d,5d,gf,mass)");
  const Geometry geo = geo_resize(in.geo);
  qassert(is_matching_geo(gf.geo, geo));
  out.init(geo);
  set_zero(out);
  const int ls = in.geo.multiplicity;
  qassert(out.geo.multiplicity == ls);
  const std::array<SpinMatrix,4>& gammas = SpinMatrixConstants::get_cps_gammas();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  std::array<SpinMatrix,4> p_mu_p;
  std::array<SpinMatrix,4> p_mu_m;
  for (int mu = 0; mu < 4; ++mu) {
    p_mu_p[mu] = 0.5 * (unit + gammas[mu]);
    p_mu_m[mu] = 0.5 * (unit - gammas[mu]);
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    Vector<WilsonVector> v = out.get_elems(xl);
    {
      const Vector<WilsonVector> iv = in.get_elems_const(xl);
      for (int m = 0; m < ls; ++m) {
        v[m] = (4.0 + mass) * iv[m];
      }
    }
    for (int mu = 0; mu < 4; ++mu) {
      const Coordinate xl_p = coordinate_shifts(xl, mu);
      const Coordinate xl_m = coordinate_shifts(xl, -mu-1);
      const ColorMatrix u_p = gf.get_elem(xl, mu);
      const ColorMatrix u_m = matrix_adjoint(gf.get_elem(xl_m, mu));
      const Vector<WilsonVector> iv_p = in.get_elems_const(xl_p);
      const Vector<WilsonVector> iv_m = in.get_elems_const(xl_m);
      for (int m = 0; m < ls; ++m) {
        v[m] -= u_p * (p_mu_m[mu] * iv_p[m]);
        v[m] -= u_m * (p_mu_p[mu] * iv_m[m]);
      }
    }
  }
}

inline void multiply_d_minus(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv)
{
  TIMER("multiply_d_minus(5d,5d,Inv)");
  const Geometry geo = geo_resize(in.geo);
  out.init(geo);
  set_zero(out);
  const FermionAction& fa = inv.fa;
  qassert(is_matching_geo(inv.geo, in.geo));
  qassert(is_matching_geo(inv.geo, out.geo));
  qassert(in.geo.multiplicity == fa.ls);
  qassert(out.geo.multiplicity == fa.ls);
  qassert(fa.bs.size() == fa.ls);
  qassert(fa.cs.size() == fa.ls);
  const GaugeField& gf = inv.gf;
  const Geometry geo1 = geo_resize(in.geo, 1);
  FermionField5d in1;
  in1.init(geo1);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    Vector<WilsonVector> v = out.get_elems(xl);
    Vector<WilsonVector> v1 = in1.get_elems(xl);
    const Vector<WilsonVector> iv = in.get_elems_const(xl);
    for (int m = 0; m < fa.ls; ++m) {
      const Complex& c = fa.cs[m];
      v1[m] = c * iv[m];
      v[m] -= iv[m];
    }
  }
  refresh_expanded_1(in1);
  FermionField5d out1;
  multiply_wilson_d_no_comm(out1, in1, gf, -fa.m5);
  out += out1;
}

inline void multiply_m(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv)
  // out can be the same object as in
{
  TIMER("multiply_m(5d,5d,Inv)");
  const Geometry geo = geo_resize(in.geo);
  out.init(geo);
  set_zero(out);
  const FermionAction& fa = inv.fa;
  qassert(is_matching_geo(inv.geo, in.geo));
  qassert(is_matching_geo(inv.geo, out.geo));
  qassert(geo.multiplicity == fa.ls);
  qassert(in.geo.multiplicity == fa.ls);
  qassert(out.geo.multiplicity == fa.ls);
  qassert(fa.bs.size() == fa.ls);
  qassert(fa.cs.size() == fa.ls);
  const SpinMatrix& gamma5 = SpinMatrixConstants::get_gamma5();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  const SpinMatrix p_p = 0.5 * (unit + gamma5);
  const SpinMatrix p_m = 0.5 * (unit - gamma5);
  const GaugeField& gf = inv.gf;
  const Geometry geo1 = geo_resize(in.geo, 1);
  FermionField5d in1, fftmp;
  in1.init(geo1);
  fftmp.init(geo);
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Vector<WilsonVector> iv = in.get_elems_const(xl);
    Vector<WilsonVector> v = fftmp.get_elems(xl);
    Vector<WilsonVector> v1 = in1.get_elems(xl);
    for (int m = 0; m < fa.ls; ++m) {
      const Complex& b = fa.bs[m];
      const Complex& c = fa.cs[m];
      v1[m] = b * iv[m];
      v[m] = iv[m];
      const WilsonVector tmp =
        (p_m * (m < fa.ls-1 ? iv[m+1] : (WilsonVector)(-fa.mass * iv[0]))) +
        (p_p * (m > 0 ? iv[m-1] : (WilsonVector)(-fa.mass * iv[fa.ls-1])));
      v1[m] += c * tmp;
      v[m] -= tmp;
    }
  }
  refresh_expanded_1(in1);
  multiply_wilson_d_no_comm(out, in1, gf, -fa.m5);
  out += fftmp;
}

inline void get_half_fermion(FermionField5d& half, const FermionField5d& ff, const int eo)
{
  TIMER("get_half_fermion");
  Geometry geoh = geo_resize(ff.geo);
  geoh.eo = eo;
  half.init(geoh);
  qassert(half.geo.eo == eo);
  qassert(ff.geo.eo == 0);
  qassert(is_matching_geo(ff.geo, half.geo));
#pragma omp parallel for
  for (long index = 0; index < geoh.local_volume(); ++index) {
    const Coordinate xl = geoh.coordinate_from_index(index);
    assign(half.get_elems(xl), ff.get_elems_const(xl));
  }
}

inline void set_half_fermion(FermionField5d& ff, const FermionField5d& half, const int eo)
{
  TIMER("set_half_fermion");
  const Geometry geoh = half.geo;
  Geometry geo = geo_resize(geoh);
  geo.eo = 0;
  ff.init(geo);
  qassert(half.geo.eo == eo);
  qassert(ff.geo.eo == 0);
  qassert(is_matching_geo(ff.geo, half.geo));
#pragma omp parallel for
  for (long index = 0; index < geoh.local_volume(); ++index) {
    const Coordinate xl = geoh.coordinate_from_index(index);
    assign(ff.get_elems(xl), half.get_elems_const(xl));
  }
}

inline void multiply_m_e_e(FermionField5d& out, const FermionField5d& in, const FermionAction& fa)
  // works for _o_o as well
{
  TIMER("multiply_m_e_e");
  out.init(geo_resize(in.geo));
  qassert(is_matching_geo(out.geo, in.geo));
  qassert(out.geo.eo == in.geo.eo);
  qassert(in.geo.eo == 1 or in.geo.eo == 2);
  const SpinMatrix& gamma5 = SpinMatrixConstants::get_gamma5();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  const SpinMatrix p_p = 0.5 * (unit + gamma5);
  const SpinMatrix p_m = 0.5 * (unit - gamma5);
  FermionField5d in_copy;
  ConstHandle<FermionField5d> hin;
  if (&out != &in) {
    hin.init(in);
  } else {
    in_copy.init(geo_resize(in.geo));
    in_copy = in;
    hin.init(in_copy);
  }
  const Geometry& geo = out.geo;
  std::vector<Complex> bee(fa.ls), cee(fa.ls);
  for (int m = 0; m < fa.ls; ++m) {
    bee[m] = 1.0 + fa.bs[m] * (4.0 - fa.m5);
    cee[m] = 1.0 - fa.cs[m] * (4.0 - fa.m5);
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Vector<WilsonVector> iv = hin().get_elems_const(xl);
    Vector<WilsonVector> v = out.get_elems(xl);
    for (int m = 0; m < fa.ls; ++m) {
      v[m] = bee[m] * iv[m];
      const WilsonVector tmp =
        (p_m * (m < fa.ls-1 ? iv[m+1] : (WilsonVector)(-fa.mass * iv[0]))) +
        (p_p * (m > 0 ? iv[m-1] : (WilsonVector)(-fa.mass * iv[fa.ls-1])));
      v[m] -= cee[m] * tmp;
    }
  }
}

inline void multiply_m_e_e_inv(FermionField5d& out, const FermionField5d& in, const FermionAction& fa)
  // works for _o_o as well
{
  TIMER("multiply_m_e_e_inv");
  out.init(geo_resize(in.geo));
  qassert(is_matching_geo(out.geo, in.geo));
  qassert(out.geo.eo == in.geo.eo);
  qassert(in.geo.eo == 1 or in.geo.eo == 2);
  const SpinMatrix& gamma5 = SpinMatrixConstants::get_gamma5();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  const SpinMatrix p_p = 0.5 * (unit + gamma5);
  const SpinMatrix p_m = 0.5 * (unit - gamma5);
  const Geometry& geo = out.geo;
  std::vector<Complex> bee(fa.ls), cee(fa.ls);
  for (int m = 0; m < fa.ls; ++m) {
    bee[m] = 1.0 + fa.bs[m] * (4.0 - fa.m5);
    cee[m] = 1.0 - fa.cs[m] * (4.0 - fa.m5);
  }
  std::vector<Complex> lee(fa.ls-1), leem(fa.ls-1);
  for (int m = 0; m < fa.ls-1; ++m) {
    lee[m] = -cee[m+1] / bee[m];
    leem[m] = m == 0 ? fa.mass * cee[fa.ls-1] / bee[0] : leem[m-1] * cee[m-1] / bee[m];
  }
  std::vector<Complex> dee(fa.ls, 0.0);
  dee[fa.ls-1] = fa.mass * cee[fa.ls-1];
  for (int m = 0; m < fa.ls-1; ++m) {
    dee[fa.ls-1] *= cee[m] / bee[m];
  }
  for (int m = 0; m < fa.ls; ++m) {
    dee[m] += bee[m];
  }
  std::vector<Complex> uee(fa.ls-1), ueem(fa.ls-1);
  for (int m = 0; m < fa.ls-1; ++m) {
    uee[m] = -cee[m] / bee[m];
    ueem[m] = m == 0 ? fa.mass * cee[0] / bee[0] : leem[m-1] * cee[m] / bee[m];
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Vector<WilsonVector> iv = in.get_elems_const(xl);
    Vector<WilsonVector> v = out.get_elems(xl);
    std::memcpy(v.data(), iv.data(), iv.data_size());
    WilsonVector tmp;
    set_zero(tmp);
    // {L^m_{ee}}^{-1}
    for (int m = 0; m < fa.ls-1; ++m) {
      tmp += (-leem[m]) * v[m];
    }
    v[fa.ls-1] += p_m * tmp;
    // {L'_{ee}}^{-1}
    for (int m = 1; m < fa.ls; ++m) {
      v[m] += (-lee[m-1]) * p_p * v[m-1];
    }
    // {D_{ee}}^{-1}
    for (int m = 0; m < fa.ls; ++m) {
      v[m] *= 1.0 / dee[m];
    }
    // {U^'_{ee}}^{-1}
    for (int m = fa.ls-2; m >= 0; --m) {
      v[m] += (-uee[m]) * p_m * v[m+1];
    }
    // {U^m_{ee}}^{-1}
    for (int m = 0; m < fa.ls-1; ++m) {
      v[m] += (-leem[m]) * p_p * v[fa.ls-1];
    }
  }
}

inline void multiply_wilson_d_e_o_no_comm(FermionField5d& out, const FermionField5d& in, const GaugeField& gf)
  // set_left_expanded_gauge_field(gf, gf_);
  // in.geo = geo_reform(geo, 1, ls);
  // refresh_expanded_1(in);
{
  TIMER("multiply_wilson_d_e_o_no_comm(5d,5d,gf)");
  qassert(is_matching_geo(gf.geo, in.geo));
  qassert(in.geo.eo == 1 or in.geo.eo == 2);
  Geometry geo = geo_resize(in.geo);
  geo.eo = 3 - in.geo.eo;
  out.init(geo);
  set_zero(out);
  const int ls = in.geo.multiplicity;
  qassert(out.geo.multiplicity == ls);
  qassert(is_matching_geo(out.geo, in.geo));
  qassert(out.geo.eo != in.geo.eo);
  qassert(out.geo.eo == 1 or out.geo.eo == 2);
  const std::array<SpinMatrix,4>& gammas = SpinMatrixConstants::get_cps_gammas();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  std::array<SpinMatrix,4> p_mu_p;
  std::array<SpinMatrix,4> p_mu_m;
  for (int mu = 0; mu < 4; ++mu) {
    p_mu_p[mu] = 0.5 * (unit + gammas[mu]);
    p_mu_m[mu] = 0.5 * (unit - gammas[mu]);
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    Vector<WilsonVector> v = out.get_elems(xl);
    for (int mu = 0; mu < 4; ++mu) {
      const Coordinate xl_p = coordinate_shifts(xl, mu);
      const Coordinate xl_m = coordinate_shifts(xl, -mu-1);
      const ColorMatrix u_p = gf.get_elem(xl, mu);
      const ColorMatrix u_m = matrix_adjoint(gf.get_elem(xl_m, mu));
      const Vector<WilsonVector> iv_p = in.get_elems_const(xl_p);
      const Vector<WilsonVector> iv_m = in.get_elems_const(xl_m);
      for (int m = 0; m < ls; ++m) {
        v[m] -= u_p * (p_mu_m[mu] * iv_p[m]);
        v[m] -= u_m * (p_mu_p[mu] * iv_m[m]);
      }
    }
  }
}

inline void multiply_m_e_o(FermionField5d& out, const FermionField5d& in, const GaugeField& gf, const FermionAction& fa)
  // works for _o_e as well
{
  TIMER("multiply_m_e_o");
  const SpinMatrix& gamma5 = SpinMatrixConstants::get_gamma5();
  const SpinMatrix& unit = SpinMatrixConstants::get_unit();
  const SpinMatrix p_p = 0.5 * (unit + gamma5);
  const SpinMatrix p_m = 0.5 * (unit - gamma5);
  FermionField5d in1;
  in1.init(geo_resize(in.geo, 1));
  const Geometry& geo = in.geo;
  std::vector<Complex> beo(fa.ls), ceo(fa.ls);
  for (int m = 0; m < fa.ls; ++m) {
    beo[m] = fa.bs[m];
    ceo[m] = -fa.cs[m];
  }
#pragma omp parallel for
  for (long index = 0; index < geo.local_volume(); ++index) {
    const Coordinate xl = geo.coordinate_from_index(index);
    const Vector<WilsonVector> iv = in.get_elems_const(xl);
    Vector<WilsonVector> v = in1.get_elems(xl);
    for (int m = 0; m < fa.ls; ++m) {
      v[m] = beo[m] * iv[m];
      const WilsonVector tmp =
        (p_m * (m < fa.ls-1 ? iv[m+1] : (WilsonVector)(-fa.mass * iv[0]))) +
        (p_p * (m > 0 ? iv[m-1] : (WilsonVector)(-fa.mass * iv[fa.ls-1])));
      v[m] -= ceo[m] * tmp;
    }
  }
  refresh_expanded_1(in1);
  multiply_wilson_d_e_o_no_comm(out, in1, gf);
  qassert(is_matching_geo(out.geo, in.geo));
  qassert(out.geo.eo != in.geo.eo);
  qassert(in.geo.eo == 1 or in.geo.eo == 2);
  qassert(out.geo.eo == 1 or out.geo.eo == 2);
}

inline void multiply_m_eo_eo(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv,
    const int eo_out, const int eo_in)
  // out need to be initialized with correct geo and eo
{
  TIMER("multiply_m_eo_eo");
  Geometry geo = geo_resize(in.geo);
  geo.eo = eo_out;
  out.init(geo);
  qassert(is_matching_geo(out.geo, in.geo));
  qassert(out.geo.eo == eo_out);
  qassert(in.geo.eo == eo_in);
  const FermionAction& fa = inv.fa;
  if (eo_out == eo_in) {
    multiply_m_e_e(out, in, fa);
  } else {
    multiply_m_e_o(out, in, inv.gf, fa);
  }
}

inline void project_eo(FermionField5d& ff, const int eo)
{
  TIMER("project_eo");
  qassert(eo == 1 or eo == 2);
  FermionField5d half;
  get_half_fermion(half, ff, eo);
  set_zero(ff);
  set_half_fermion(ff, half, eo);
}

inline void multiply_m_from_eo(FermionField5d& out, const FermionField5d& in, const InverterDomainWall& inv)
{
  TIMER_VERBOSE("multiply_m_from_eo");
  FermionField5d in_e, in_o;
  get_half_fermion(in_e, in, 2);
  get_half_fermion(in_o, in, 1);
  FermionField5d out1_e, out1_o;
  FermionField5d out_e, out_o;
  multiply_m_eo_eo(out1_e, in_e, inv, 2, 2);
  multiply_m_eo_eo(out1_o, in_e, inv, 1, 2);
  multiply_m_eo_eo(out_e, in_o, inv, 2, 1);
  multiply_m_eo_eo(out_o, in_o, inv, 1, 1);
  out_e += out1_e;
  out_o += out1_o;
  set_half_fermion(out, out_e, 2);
  set_half_fermion(out, out_o, 1);
}

inline bool& is_checking_inverse()
  // qlat parameter
{
  static bool b = false;
  return b;
}

QLAT_END_NAMESPACE