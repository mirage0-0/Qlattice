#    Qlattice (https://github.com/waterret/qlattice)
#
#    Copyright (C) 2021
#
#    Author: Luchang Jin (ljin.luchang@gmail.com)
#    Author: Masaaki Tomii
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from auto_contractor.compile import *
import gpt as g
import numpy as np
import qlat as q
import copy
import cmath
import math

@q.timer
def get_prop_psnk_psrc(prop_get, flavor : str, xg_snk, xg_src):
    return prop_get(flavor, xg_snk, xg_src)

def get_spin_matrix(op):
    assert op.otype == "G"
    assert op.s1 == "auto" and op.s2 == "auto"
    assert op.tag in [0, 1, 2, 3, 5]
    return g.gamma[op.tag]

def ascontiguoustensor(tensor):
    return g.tensor(np.ascontiguousarray(tensor.array), tensor.otype)

def eval_op_term_expr(expr, variable_dict, positions_dict, prop_get):
    def l_eval(x):
        if isinstance(x, list):
            ans = l_eval(x[0])
            for op in x[1:]:
                ans = ascontiguoustensor(ans * l_eval(op))
            return ans
        elif isinstance(x, Op):
            if x.otype == "S":
                flavor = x.f
                xg_snk = positions_dict[x.p1]
                xg_src = positions_dict[x.p2]
                return get_prop_psnk_psrc(prop_get, flavor, xg_snk, xg_src)
            elif x.otype == "G":
                return get_spin_matrix(x)
            elif x.otype == "Tr" and len(x.ops) == 2:
                return g.trace(l_eval(x.ops[0]) * l_eval(x.ops[1]))
            elif x.otype == "Tr":
                if not x.ops:
                    return 1
                start_idx = None
                for i in range(len(x.ops)):
                    if x.ops[i].otype != "G":
                        start_idx = i
                        break
                assert start_idx is not None
                ans = l_eval(x.ops[start_idx])
                for op in x.ops[start_idx + 1:] + x.ops[:start_idx]:
                    ans = ascontiguoustensor(ans * l_eval(op))
                return g.trace(ans)
            elif x.otype == "Var":
                return variable_dict[x.name]
            else:
                q.displayln_info(f"eval_op_term_expr: ERROR: l_eval({x})")
                assert False
        elif isinstance(x, Term):
            assert not x.a_ops
            ans = x.coef
            for op in x.c_ops:
                ans = ans * l_eval(op)
            return ans
        elif isinstance(x, Expr):
            ans = 0
            for term in x.terms:
                ans = ans + l_eval(term)
            return ans
        else:
            q.displayln_info(f"eval_op_term_expr: ERROR: l_eval({x})")
            assert False
    return g.eval(l_eval(expr))

@q.timer
def eval_cexpr(cexpr : CExpr, *, positions_dict, prop_get, is_only_total):
    # interface function
    # the last element is the sum
    for pos in cexpr.positions:
        assert pos in positions_dict
    variable_dict = {}
    for name, op in cexpr.variables:
        variable_dict[name] = eval_op_term_expr(op, variable_dict, positions_dict, prop_get)
    tvals = { name : eval_op_term_expr(term, variable_dict, positions_dict, prop_get) for name, term in cexpr.named_terms }
    evals = { name : sum([ tvals[tname] for tname in expr ]) for name, expr in cexpr.named_exprs }
    if is_only_total in [ True, "total", ]:
        return np.array([ evals[name] for name, expr in cexpr.named_exprs])
    elif is_only_total in [ "typed_total", ]:
        tevals = { name : sum([ tvals[tname] for tname in expr ]) for name, expr in cexpr.named_typed_exprs }
        return np.array([ tevals[name] for name, expr in cexpr.named_typed_exprs ] + [ evals[name] for name, expr in cexpr.named_exprs])
    elif is_only_total in [ False, "term", ]:
        tevals = { name : sum([ tvals[tname] for tname in expr ]) for name, expr in cexpr.named_typed_exprs }
        return np.array([ tvals[name] for name, term in cexpr.named_terms ] + [ tevals[name] for name, expr in cexpr.named_typed_exprs ] + [ evals[name] for name, expr in cexpr.named_exprs])
    else:
        assert False

def sqr_component(x):
    return x.real * x.real + 1j * x.imag * x.imag

def sqrt_component(x):
    return math.sqrt(x.real) + 1j * math.sqrt(x.imag)

def sqr_component_array(arr):
    return np.array([ sqr_component(x) for x in arr ])

def sqrt_component_array(arr):
    return np.array([ sqrt_component(x) for x in arr ])

@q.timer
def eval_cexpr_simulation(cexpr : CExpr, *, positions_dict_maker, rng_state, trial_indices, total_site, prop_get, is_only_total):
    # interface function
    results = None
    num_fac = None
    for idx in trial_indices:
        rs = rng_state.split(str(idx))
        positions_dict, facs = positions_dict_maker(idx, rs, total_site)
        if num_fac is None:
            num_fac = len(facs)
            results = [ [] for i in range(num_fac) ]
        else:
            assert num_fac == len(facs)
        res = eval_cexpr(cexpr, positions_dict = positions_dict, prop_get = prop_get , is_only_total = is_only_total)
        for i in range(num_fac):
            results[i].append(facs[i] * res)
    summaries = []
    for i in range(num_fac):
        assert len(results[i]) == len(trial_indices)
        results_avg = sum(results[i]) / len(trial_indices)
        results_err = sqrt_component_array(sum([ sqr_component_array(r - results_avg) for r in results[i] ])) / len(trial_indices)
        if is_only_total in [ True, "total", ]:
            names = [ name for name, expr in cexpr.named_exprs ]
        elif is_only_total in [ "typed_total", ]:
            names = [ name for name, expr in cexpr.named_typed_exprs ] + [ name for name, expr in cexpr.named_exprs ]
        elif is_only_total in [ False, "term", ]:
            names = [ name for name, term in cexpr.named_terms ] + [ name for name, expr in cexpr.named_typed_exprs ] + [ name for name, expr in cexpr.named_exprs ]
        else:
            assert False
        summary = {}
        for i in range(len(names)):
            summary[names[i]] = [results_avg[i], results_err[i],]
        summaries.append(summary)
    return summaries

@q.timer
def positions_dict_maker_example_1(idx, rs, total_site):
    t2 = 3
    x1 = rs.c_rand_gen(total_site)
    x2 = rs.c_rand_gen(total_site)
    x2[3] = (x1[3] + t2) % total_site[3]
    pd = {
            "x1" : x1,
            "x2" : x2,
            }
    facs = [1.0,]
    return pd, facs

@q.timer
def positions_dict_maker_example_2(idx, rs, total_site):
    lmom1 = [0.0, 0.0, 1.0, 0.0,]
    lmom2 = [0.0, 0.0, -1.0, 0.0,]
    t2 = 2
    t3 = 5
    x1 = rs.c_rand_gen(total_site)
    x2 = rs.c_rand_gen(total_site)
    x3 = rs.c_rand_gen(total_site)
    x2[3] = (x1[3] + t2) % total_site[3]
    x3[3] = (x1[3] + t3) % total_site[3]
    pd = {
            "x1" : x1,
            "x2" : x2,
            "x3" : x3,
            }
    phase = 0.0
    for mu in range(4):
        mom1 = 2.0 * math.pi / total_site[mu] * lmom1[mu]
        mom2 = 2.0 * math.pi / total_site[mu] * lmom2[mu]
        phase += mom1 * x1[mu]
        phase += mom2 * x2[mu]
    facs = [1.0, cmath.rect(1.0, phase),]
    return pd, facs

if __name__ == "__main__":
    rs = q.RngState("3")
    q.displayln_info(rs)
    total_site = [4, 4, 4, 16,]
    print(positions_dict_maker_example_1(0, rs, total_site))
    print(positions_dict_maker_example_2(0, rs, total_site))
    print(CExpr([('S_1', S('d','x2','x1')), ('S_2', S('u','x1','x2'))],[('T_1', Term([Tr([G(5), Var('S_1'), G(5), Var('S_2')],'sc')],[],(-1+0j)))],['x1', 'x2']))

