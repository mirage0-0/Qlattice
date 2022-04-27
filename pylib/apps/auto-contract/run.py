#!/usr/bin/env python3

from auto_contractor.operators import *
import rbc_ukqcd as ru
import qlat_gpt as qg

from jobs import *
from load_data import *
from params import *

load_path_list[:] = [
        "results",
        "../qcddata",
        os.path.join(os.getenv("HOME"), "qcddata"),
        os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-gf-gt/results"),
        os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-sel/results"),
        os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-fsel-self-loop/results"),
        os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-selected-data/results"),
        # os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-wsrc-prop/results"),
        # os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-psrc-prop/results"),
        os.path.join(os.getenv("HOME"), "Qlat-sample-data/default/mk-smear-prop/results"),
        ]

def rel_mod(x, size):
    x = (x + 2 * size) % size
    assert x >= 0
    if 2 * x >= size:
        return x - size
    else:
        return x

### ------

import multiprocessing as mp

pool_function = None

def call_pool_function(*args, **kwargs):
    assert pool_function is not None
    return pool_function(*args, **kwargs)

def parallel_map(n_processes, func, iterable):
    if n_processes == 0:
        return list(map(func, iterable))
    global pool_function
    pool_function = func
    with mp.Pool(n_processes) as p:
        res = p.map(call_pool_function, iterable)
    pool_function = None
    return res

### ------

@q.timer
def get_cexpr_vev():
    def calc_cexpr():
        s = new_spin_index()
        c = new_color_index()
        p = "x"
        exprs = [
                Qb("u", "x", s, c) * Qv("u", "x", s, c) + "u_bar*u",
                Qb("s", "x", s, c) * Qv("s", "x", s, c) + "s_bar*s",
                Qb("c", "x", s, c) * Qv("c", "x", s, c) + "c_bar*c",
                ]
        cexpr = contract_simplify_compile(*exprs, is_isospin_symmetric_limit = True)
        q.displayln_info(display_cexpr(cexpr))
        cexpr.collect_op()
        return cexpr
    cexpr = q.pickle_cache_call(calc_cexpr, f"cache/auto_contractor_cexpr/vev-cexpr.pickle")
    q.displayln_info(display_cexpr_raw(cexpr))
    return cexpr

@q.timer_verbose
def auto_contractor_vev(job_tag, traj, get_prop, get_psel, get_fsel):
    fn = f"auto-contractor-fsel/{job_tag}/traj={traj}/vev.lat"
    if get_load_path(fn) is not None:
        return
    cexpr = get_cexpr_vev()
    names_expr = get_cexpr_names(cexpr)
    fsel, fselc = get_fsel()
    xg_fsel_list = fsel.to_psel_local().to_list()
    def feval(x):
        pd = {
                "x" : ("point-snk", x,),
                }
        res = eval_cexpr(cexpr, positions_dict = pd, get_prop = get_prop, is_only_total = "total")
        return res
    res_list = parallel_map(0, feval, xg_fsel_list)
    res_sum = q.glb_sum(sum(res_list))
    res_count = q.glb_sum(len(res_list))
    res_avg = res_sum / res_count
    ld = q.mk_lat_data([
        [ "expr_name", len(names_expr), names_expr, ],
        ])
    ld.from_numpy(res_avg)
    q.displayln_info(ld.show())
    ld.save(get_save_path(fn))

@q.timer
def get_cexpr_meson_corr():
    def calc_cexpr():
        exprs = [
                mk_pi_p("x2", True) * mk_pi_p("x1") + "(pi     * pi)",
                -1j * mk_j5pi_mu("x2", 3) * mk_pi_p("x1") + "(a_pi/i * pi)",
                mk_k_p("x2", True)  * mk_k_p("x1")  + "(k      * k )",
                -1j * mk_j5k_mu("x2", 3)  * mk_k_p("x1")  + "(a_k/i  * k )",
                ]
        cexpr = contract_simplify_compile(*exprs, is_isospin_symmetric_limit = True)
        q.displayln_info(display_cexpr(cexpr))
        cexpr.collect_op()
        return cexpr
    cexpr = q.pickle_cache_call(calc_cexpr, f"cache/auto_contractor_cexpr/meson_corr-cexpr.pickle")
    q.displayln_info(display_cexpr_raw(cexpr))
    return cexpr

@q.timer_verbose
def auto_contractor_meson_corr(job_tag, traj, get_prop, get_psel, get_fsel):
    fn = f"auto-contractor-fsel/{job_tag}/traj={traj}/meson_corr.lat"
    if get_load_path(fn) is not None:
        return
    cexpr = get_cexpr_meson_corr()
    names_expr = get_cexpr_names(cexpr)
    total_site = ru.get_total_site(job_tag)
    fsel, fselc = get_fsel()
    xg_fsel_list = fsel.to_psel_local().to_list()
    def feval(x):
        l = []
        for t in range(total_site[3]):
            pd = {
                    "x2" : ("point-snk", x,),
                    "x1" : ("wall", (x[3] - t) % total_site[3],),
                    }
            res = eval_cexpr(cexpr, positions_dict = pd, get_prop = get_prop, is_only_total = "total")
            l.append(res)
        return np.array(l).transpose()
    res_list = parallel_map(0, feval, xg_fsel_list)
    res_sum = q.glb_sum(sum(res_list))
    res_count = q.glb_sum(len(res_list))
    res_avg = res_sum / res_count
    ld = q.mk_lat_data([
        [ "expr_name", len(names_expr), names_expr, ],
        [ "t_sep", total_site[3], ],
        ])
    ld.from_numpy(res_avg)
    q.displayln_info(ld.show())
    ld.save(get_save_path(fn))

@q.timer
def get_cexpr_hvp():
    def calc_cexpr():
        exprs = [
                -mk_jl_mu("x2", 0) * mk_jl_mu("x1", 0) + "(-jl_0 * jl_0)",
                -mk_jl_mu("x2", 1) * mk_jl_mu("x1", 1) + "(-jl_1 * jl_1)",
                -mk_jl_mu("x2", 2) * mk_jl_mu("x1", 2) + "(-jl_2 * jl_2)",
                -mk_jl_mu("x2", 3) * mk_jl_mu("x1", 3) + "(-jl_3 * jl_3)",
                -mk_jl_mu("x2", 5) * mk_jl_mu("x1", 5) + "(-jl_5 * jl_5)",
                ]
        cexpr = contract_simplify_compile(*exprs, is_isospin_symmetric_limit = True)
        q.displayln_info(display_cexpr(cexpr))
        cexpr.collect_op()
        return cexpr
    cexpr = q.pickle_cache_call(calc_cexpr, f"cache/auto_contractor_cexpr/hvp-cexpr.pickle")
    q.displayln_info(display_cexpr_raw(cexpr))
    return cexpr

@q.timer_verbose
def auto_contractor_hvp(job_tag, traj, get_prop, get_psel, get_fsel):
    fn = f"auto-contractor-fsel/{job_tag}/traj={traj}/hvp.lat"
    if get_load_path(fn) is not None:
        return
    cexpr = get_cexpr_hvp()
    names_expr = get_cexpr_names(cexpr)
    total_site = ru.get_total_site(job_tag)
    psel = get_psel()
    fsel, fselc = get_fsel()
    xg_fsel_list = fsel.to_psel_local().to_list()
    xg_psel_list = psel.to_list()
    vol = total_site[0] * total_site[1] * total_site[2]
    def feval(xg_src):
        counts = np.zeros(total_site[3], dtype = int)
        values = np.zeros((total_site[3], len(names_expr)), dtype = complex)
        for xg_snk in xg_fsel_list:
            pd = {
                    "x2" : ("point-snk", xg_snk,),
                    "x1" : ("point", xg_src,),
                    }
            res = eval_cexpr(cexpr, positions_dict = pd, get_prop = get_prop, is_only_total = "total")
            tsep = (xg_snk[3] - xg_src[3]) % total_site[3]
            counts[tsep] += 1
            values[tsep] += res
        counts = counts # counts[tsep]
        values = values.transpose() # values[expr_idx, tsep]
        return counts, values
    counts_list, values_list = zip(*parallel_map(0, feval, xg_psel_list))
    res_count = q.glb_sum(sum(counts_list))
    res_sum = q.glb_sum(sum(values_list))
    res_avg = res_sum * (vol / res_count)
    ld = q.mk_lat_data([
        [ "expr_name", len(names_expr), names_expr, ],
        [ "t_sep", total_site[3], ],
        ])
    ld.from_numpy(res_avg)
    q.displayln_info(ld.show())
    ld.save(get_save_path(fn))

@q.timer_verbose
def auto_contractor_hvp_field(job_tag, traj, get_prop, get_psel, get_fsel):
    fn = f"auto-contractor-fsel/{job_tag}/traj={traj}/hvp.field"
    if get_load_path(fn) is not None:
        return
    cexpr = get_cexpr_hvp()
    names_expr = get_cexpr_names(cexpr)
    total_site = ru.get_total_site(job_tag)
    psel = get_psel()
    fsel, fselc = get_fsel()
    xg_fsel_list = fsel.to_psel_local().to_list()
    xg_psel_list = psel.to_list()
    geo = q.Geometry(total_site, 1)
    field = q.Field("Complex", geo, len(names_expr))
    field.set_zero()
    for idx, xg_src in enumerate(xg_psel_list):
        def feval(xg_snk):
            pd = {
                    "x2" : ("point-snk", xg_snk,),
                    "x1" : ("point", xg_src,),
                    }
            res = eval_cexpr(cexpr, positions_dict = pd, get_prop = get_prop, is_only_total = "total")
            return res
        values_list = parallel_map(0, feval, xg_fsel_list)
        assert len(values_list) == fsel.n_elems()
        values = q.SelectedField("Complex", fsel, len(names_expr))
        for idx, v in enumerate(values_list):
            values[idx] = v.tobytes()
        shift = [ -x for x in xg_src ]
        values_shifted = values.field_shift(shift)
        field += values_shifted
    # scale the value appropriately
    field *= 1.0 / (len(xg_psel_list) * fsel.prob())
    field.save_float_from_double(get_save_path(fn))
    q.displayln_info(field.glb_sum_tslice().to_numpy())

### ------

@q.timer_verbose
def run_job(job_tag, traj):
    fns_produce = [
            f"auto-contractor-fsel/{job_tag}/traj={traj}/checkpoint.txt",
            ]
    fns_need = [
            (f"configs/{job_tag}/ckpoint_lat.{traj}", f"configs/{job_tag}/ckpoint_lat.IEEE64BIG.{traj}",),
            f"point-selection/{job_tag}/traj={traj}.txt",
            f"field-selection/{job_tag}/traj={traj}.field",
            f"gauge-transform/{job_tag}/traj={traj}.field",
            f"wall-src-info-light/{job_tag}/traj={traj}.txt",
            f"wall-src-info-strange/{job_tag}/traj={traj}.txt",
            f"prop-wsrc-strange/{job_tag}/traj={traj}/geon-info.txt",
            f"psel-prop-wsrc-strange/{job_tag}/traj={traj}/checkpoint.txt",
            f"prop-wsrc-light/{job_tag}/traj={traj}/geon-info.txt",
            f"psel-prop-wsrc-light/{job_tag}/traj={traj}/checkpoint.txt",
            f"prop-psrc-strange/{job_tag}/traj={traj}/geon-info.txt",
            f"psel-prop-psrc-strange/{job_tag}/traj={traj}/checkpoint.txt",
            f"prop-psrc-light/{job_tag}/traj={traj}/geon-info.txt",
            f"psel-prop-psrc-light/{job_tag}/traj={traj}/checkpoint.txt",
            f"prop-rand-u1-light/{job_tag}/traj={traj}/geon-info.txt",
            f"prop-rand-u1-strange/{job_tag}/traj={traj}/geon-info.txt",
            f"prop-rand-u1-charm/{job_tag}/traj={traj}/geon-info.txt",
            ]
    if not check_job(job_tag, traj, fns_produce, fns_need):
        return
    #
    traj_gf = traj
    if job_tag[:5] == "test-":
        # ADJUST ME
        traj_gf = 1000
        #
    #
    get_gf = run_gf(job_tag, traj_gf)
    get_gt = run_gt(job_tag, traj_gf, get_gf)
    #
    get_psel = run_psel(job_tag, traj)
    get_fsel = run_fsel(job_tag, traj, get_psel)
    #
    get_wi = run_wi(job_tag, traj)
    get_psel_smear = run_psel_smear(job_tag, traj)
    #
    get_get_prop = run_get_prop(job_tag, traj,
            get_gt = get_gt,
            get_psel = get_psel,
            get_fsel = get_fsel,
            get_psel_smear = get_psel_smear,
            get_wi = get_wi,
            )
    #
    fn_checkpoint = f"auto-contractor-fsel/{job_tag}/traj={traj}/checkpoint.txt"
    if get_load_path(fn_checkpoint) is None:
        if q.obtain_lock(f"locks/{job_tag}-{traj}-auto-contractor"):
            get_prop = get_get_prop()
            # ADJUST ME
            auto_contractor_vev(job_tag, traj, get_prop, get_psel, get_fsel)
            auto_contractor_meson_corr(job_tag, traj, get_prop, get_psel, get_fsel)
            auto_contractor_hvp(job_tag, traj, get_prop, get_psel, get_fsel)
            auto_contractor_hvp_field(job_tag, traj, get_prop, get_psel, get_fsel)
            #
            q.qtouch_info(get_save_path(fn_checkpoint))
            q.release_lock()
    #
    q.clean_cache()
    q.timer_display()

qg.begin_with_gpt()

q.qremove_all_info("locks")
q.qremove_all_info("results")
q.qremove_all_info("cache")

run_job("test-4nt8", 1000)

qg.end_with_gpt()
