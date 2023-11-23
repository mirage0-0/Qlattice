import numpy as np

from .c import *
from .utils import *
from .data import *

def mk_data_set(*, n_jk=10, n_ops=4, n_energies=4, t_size=4, sigma=0.1, rng=None):
    """
    return param_arr, jk_corr_data, corr_data_sigma
    #
    energies[ei] is float
    coefs[ei, i] is float
    corr_data[i, j, t] = \sum_{ei} coefs[ei, i] * coefs[ei, j] * \exp(-energies[ei] * t)
    jk_corr_data[jk, i, j, t] = corr_data[i, j, t] + corr_data_sigma[i, j, t] * N(0,1)
    """
    if rng is None:
        rng = RngState("mk_data_set-seed")
    #
    energies = rng.u_rand_arr((n_energies,)) * 2.0 + 0.1
    #
    coefs = rng.u_rand_arr((n_energies, n_ops)) * 2.0 - 1.0
    #
    t_arr = np.arange(t_size)
    corr_data = (coefs[:, :, None, None] * coefs[:, None, :, None]
                 * np.exp(-energies[:, None, None, None] * t_arr)
                 ).sum(0)
    corr_data_sigma = np.zeros((n_ops, n_ops, t_size,), dtype=float) + sigma
    #
    jk_corr_data = np.empty((n_jk, n_ops, n_ops, t_size,), dtype=float)
    jk_corr_data = corr_data + rng.g_rand_arr((n_jk, n_ops, n_ops, t_size,)) * corr_data_sigma
    #
    param_arr = np.concatenate([ energies, coefs.ravel(), ], dtype=float)
    return param_arr, jk_corr_data, corr_data_sigma

@timer
def mk_fcn(corr_data, corr_data_sigma, t_start):
    """
    Shape of inputs and parameters are like:
    corr_data.shape == (n_ops, n_ops, t_size,)
    corr_data_sigma.shape == (n_ops, n_ops, t_size,)
    t_start is the start tslice of the corr_data (can be energy dependent array, t_start for negative_energy ~ -t_size)
    return fcn
    fcn(param_arr) => chisq, param_grad_arr
    e.g.
    param_arr = np.concatenate([ es.ravel(), cs.ravel() ], dtype=np.float64)
    es.shape == (n_energies,)
    cs.shape == (n_energies, n_ops,)
    #
    corr_data[i, j, t] = \sum_{ei} coefs[ei, i] * coefs[ei, j] * \exp(-energies[ei] * (t + t_start[ei]))
    #
    """
    import jax
    import jax.numpy as jnp
    if jnp.zeros(2, dtype=jnp.float64).dtype != jnp.float64:
        raise Exception(f"ERROR: double precision not available in JAX. Please set: 'export JAX_ENABLE_X64=True' to use double precision number here.")
    shape = corr_data.shape
    assert shape == corr_data_sigma.shape
    assert len(shape) == 3
    n_ops = shape[0]
    assert shape[1] == n_ops
    t_size = shape[2]
    corr_avg = jnp.array(corr_data, dtype=jnp.float64)
    corr_sigma = jnp.array(corr_data_sigma, dtype=jnp.float64)
    t_arr = jnp.arange(t_size, dtype=jnp.float64)
    def fcn_f(param_arr):
        assert len(param_arr.shape) == 1
        n_params = len(param_arr)
        assert n_params % (n_ops + 1) == 0
        n_energies = n_params // (n_ops + 1)
        param_arr = jnp.array(param_arr, dtype=jnp.float64)
        es = param_arr[:n_energies]
        cs = param_arr[n_energies:].reshape(n_energies, n_ops)
        t_start_arr = np.zeros(n_energies, dtype=np.float64)
        t_start_arr[:] = t_start
        corr = (cs[:, :, None, None] * cs[:, None, :, None]
                * jnp.exp(-es[:, None, None, None] * (t_arr + t_start_arr[:, None, None, None]))
                ).sum(0)
        corr = (corr - corr_avg) / corr_sigma
        chisqs = corr * corr
        chisq = chisqs.sum()
        return chisq
    fcn_f_jit = jax.jit(fcn_f)
    fcn_fg_jit = jax.jit(jax.value_and_grad(fcn_f))
    @timer
    def fcn(param_arr, requires_grad=True):
        if requires_grad:
            chisq, grad = fcn_fg_jit(param_arr)
            return chisq, np.array(grad, dtype=np.float64)
        else:
            chisq = fcn_f_jit(param_arr)
            return chisq.item()
    return fcn

### -------------------

@timer
def minimize(fcn, n_step=10, step_size=1e-2, *, param_arr):
    chisq_pre = None
    for i in range(n_step):
        chisq, param_grad_arr = fcn(param_arr)
        grad_norm = np.linalg.norm(param_grad_arr)
        displayln_info(1, f"minimize: step={i} chisq={chisq} grad_norm={grad_norm} param_arr={param_arr}")
        if chisq_pre is not None:
            if chisq > chisq_pre:
                displayln_info(0, f"minimize: early stop step={i} step_size={step_size} chisq={chisq_pre} grad_norm={grad_norm}")
                return param_arr_pre, i
        param_arr_pre = param_arr
        chisq_pre = chisq
        param_arr = param_arr - step_size / grad_norm * param_grad_arr
    displayln_info(0, f"minimize: step={n_step} step_size={step_size} chisq={chisq_pre} grad_norm={grad_norm}")
    return param_arr_pre, n_step

@timer
def adaptive_minimize(fcn, step_size_list, n_step=10, max_total_steps=10000, *, param_arr):
    idx = 0
    total_steps = 0
    total_steps_pre = 0
    while True:
        step_size = step_size_list[idx]
        param_arr, i_step = minimize(fcn, n_step=n_step, step_size=step_size, param_arr=param_arr)
        total_steps += i_step
        if total_steps - total_steps_pre > 1000:
            displayln_info(0, f"{step_size:.8f} total_steps={total_steps}")
            total_steps_pre = total_steps
        if total_steps > max_total_steps:
            return param_arr
        if i_step == n_step:
            idx = max(idx - 1, 0)
        else:
            idx = idx + 1
            if idx == len(step_size_list):
                return param_arr

@timer
def minimize_scipy(fcn, *, param_arr, fixed_param_mask=None, minimize_kwargs=None):
    import scipy
    fname = get_fname()
    n_params = len(param_arr)
    if fixed_param_mask is None:
        fixed_param_mask = np.zeros(n_params, dtype=bool)
    p_fixed = param_arr[fixed_param_mask]
    free_param_mask = ~fixed_param_mask
    @timer
    def c_fcn(p_free):
        p_all = np.empty(n_params, dtype=np.float64)
        p_all[fixed_param_mask] = p_fixed
        p_all[free_param_mask] = p_free
        chisq = fcn(p_all, requires_grad=False)
        return chisq
    @timer
    def c_fcn_grad(p_free):
        p_all = np.empty(n_params, dtype=np.float64)
        p_all[fixed_param_mask] = p_fixed
        p_all[free_param_mask] = p_free
        chisq, grad_all = fcn(p_all, requires_grad=True)
        return grad_all[free_param_mask]
    p_free = param_arr[free_param_mask]
    if minimize_kwargs is None:
        minimize_kwargs = dict()
    if "options" not in minimize_kwargs:
        minimize_kwargs["options"] = dict(maxiter=1e3)
    if "method" not in minimize_kwargs:
        minimize_kwargs["method"] = 'BFGS'
    res = scipy.optimize.minimize(
            c_fcn,
            p_free,
            jac=c_fcn_grad,
            **minimize_kwargs,
            )
    p_free_mini = res.x
    param_arr_mini = param_arr.copy()
    param_arr_mini[free_param_mask] = p_free_mini
    displayln_info(0, f"{fname}: fun={res.fun} ; grad_norm={np.linalg.norm(res.jac)}")
    displayln_info(0, f"{fname}: success={res.success} ; message={res.message} ; nfev={res.nfev} ; njev={res.njev}")
    return param_arr_mini

### -----------------

def jk_mini_task_in_fit_energy_amplitude(kwargs):
    def f(*,
          jk_idx,
          corr_data,
          corr_data_err,
          t_start_fcn_arr,
          param_arr_mini,
          n_step_mini_jk,
          r_amp,
          rand_update_mask,
          all_energies_mask,
          fixed_energies_mask,
          minimize_kwargs,
          ):
        rng = RngState(f"jk_mini_task_in_fit_energy_amplitude-seed-param").split(f"{jk_idx}")
        n_params = len(param_arr_mini)
        def rand_update(param_arr):
            param_arr = param_arr.copy()
            param_arr[rand_update_mask] = (
                    param_arr[rand_update_mask]
                    + (rng.u_rand_arr(n_params)[rand_update_mask] - 0.5) * r_amp)
            return param_arr
        fcn = mk_fcn(corr_data, corr_data_err, t_start_fcn_arr)
        param_arr = param_arr_mini.copy()
        for i in range(n_step_mini_jk):
            param_arr = rand_update(param_arr)
            param_arr = minimize_scipy(fcn, param_arr=param_arr,
                                       fixed_param_mask=all_energies_mask,
                                       minimize_kwargs=minimize_kwargs)
        for i in range(n_step_mini_jk):
            param_arr = rand_update(param_arr)
            param_arr = minimize_scipy(fcn, param_arr=param_arr,
                                       fixed_param_mask=fixed_energies_mask,
                                       minimize_kwargs=minimize_kwargs)
        chisq, chisq_grad = fcn(param_arr)
        return chisq, chisq_grad, param_arr
    return f(**kwargs)

def mp_initializer():
    import qlat as q
    q.set_verbose_level(-1)

@timer_verbose
def fit_energy_amplitude(jk_corr_data,
                         *,
                         t_start_data=0,
                         t_start_fit=4,
                         t_stop_fit=None,
                         t_start_fcn=0,
                         fixed_energy_arr=None,
                         free_energy_arr=None,
                         c_arr=None,
                         n_step_mini_avg=10,
                         n_step_mini_jk=5,
                         minimize_kwargs=None,
                         r_amp=1e-6,
                         off_diag_err_scale_factor=1.0,
                         mp_pool=None,
                         ):
    """
    return res
    #
    res['jk_chisq'] = jk_chisq
    res['jk_chisq_grad'] = jk_chisq_grad # chisq_grad with respect to param_arr (for the scaled jk_corr_data)
    res['jk_param_arr_for_scaled_corr'] = jk_param_arr_for_scaled_corr
    res['jk_param_arr'] = jk_param_arr
    #
    C^{(jk_idx)}_{i,j}(t + t_start_data) == jk_corr_data[jk_idx, i, j, t]
    #
    jk_corr_data.shape == (n_jk, n_ops, n_ops, t_size,)
    jk_corr_data.dtype == np.float64
    #
    n_energies = len(fixed_energy_arr) + len(free_energy_arr)
    #
    e_arr == np.concatenate([ fixed_energy_arr, free_energy_arr, ], dtype=np.float64)
    e_arr.shape == (n_energies,)
    c_arr.shape == (n_energies, n_ops,)
    #
    C^{(jk_idx)}_{i,j}(t) ~ \sum_{n} c_arr[n, i] * c_arr[n, j] * exp(- e_arr[n] * t)
    #
    jk_param_arr_mini.shape == (n_jk, n_params)
    param_arr == np.concatenate([ e_arr, c_arr.ravel(), ], dtype=np.float64)
    #
    off_diag_err_scale_factor should be np.sqrt(2) if jk_corr_data has been symmetrized
    """
    fname = get_fname()
    #
    assert len(jk_corr_data.shape) == 4
    #
    if t_stop_fit is None:
        t_stop_fit = t_start_data + jk_corr_data.shape[3]
    #
    t_start = t_start_fit - t_start_data
    t_stop = t_stop_fit - t_start_data
    #
    jk_corr_data = jk_corr_data[:, :, :, t_start:t_stop].copy()
    #
    n_jk = len(jk_corr_data)
    #
    if fixed_energy_arr is None:
        fixed_energy_arr = np.array([], dtype=np.float64)
        if free_energy_arr is None:
            free_energy_arr = np.array([ 0.0, ], dtype=np.float64)
    else:
        if free_energy_arr is None:
            free_energy_arr = np.array([], dtype=np.float64)
    #
    fixed_energy_arr = fixed_energy_arr.copy()
    free_energy_arr = free_energy_arr.copy()
    #
    e_arr = np.concatenate([ fixed_energy_arr, free_energy_arr ])
    n_fixed_energies = len(fixed_energy_arr)
    n_free_energies = len(free_energy_arr)
    n_energies = len(e_arr)
    #
    t_start_fcn_arr = np.zeros(n_energies, dtype=np.float64)
    t_start_fcn_arr[:] = t_start_fcn
    #
    n_ops = jk_corr_data.shape[1]
    assert n_ops == jk_corr_data.shape[2]
    #
    op_idx_arr = np.arange(n_ops)
    op_norm_fac = 1 / np.sqrt(jk_corr_data[0, op_idx_arr, op_idx_arr, 0])
    jk_corr_data = op_norm_fac[:, None, None] * op_norm_fac[None, :, None] * jk_corr_data
    #
    if n_step_mini_jk == 0:
        mp_pool = None
    #
    is_close_pool = False
    if mp_pool is None:
        mp_map = map
        mp_pool_n_proc = 1
    elif isinstance(mp_pool, int):
        mp_pool_n_proc = mp_pool
        import multiprocessing
        mp_pool = multiprocessing.get_context('spawn').Pool(mp_pool_n_proc, initializer=mp_initializer)
        mp_map = mp_pool.imap
        is_close_pool = True
    else:
        mp_pool_n_proc = 16
        mp_map = mp_pool.imap
    #
    corr_data, corr_data_err = g_jk_avg_err(jk_corr_data)
    #
    isfinite_sel = np.isfinite(corr_data)
    jk_corr_data[:, ~isfinite_sel] = 0.0
    corr_data[~isfinite_sel] = 0.0
    corr_data_err[~isfinite_sel] = np.inf
    #
    is_zero_err_sel = corr_data_err == 0.0
    corr_data_err[is_zero_err_sel] = 1.0
    #
    # corr_data_err[op1_idx, op2_idx, t_idx]
    op_idx_arr = np.arange(n_ops)
    op_op_off_diag_sel = op_idx_arr[:, None] != op_idx_arr[None, :]
    corr_data_err[op_op_off_diag_sel] *= off_diag_err_scale_factor
    #
    fcn_avg = mk_fcn(corr_data, corr_data_err, t_start_fcn_arr)
    #
    if c_arr is None:
        c_arr = np.zeros((n_energies, n_ops,), dtype=np.float64)
    else:
        assert c_arr.shape == (n_energies, n_ops,)
        c_arr = c_arr * op_norm_fac * np.exp(-e_arr[:, None] * (t_start_fit - t_start_fcn_arr[:, None]) / 2)
    #
    param_arr_initial = np.concatenate([ e_arr, c_arr.ravel(), ], dtype=np.float64)
    #
    n_params = len(param_arr_initial)
    #
    all_energies_mask = np.arange(n_params) < n_energies
    fixed_energies_mask = np.arange(n_params) < n_fixed_energies
    rand_update_mask = np.arange(n_params) >= n_energies
    #
    def display_param_arr(param_arr, fcn, mask=None, verbose_level=0):
        fcn, grad = fcn(param_arr)
        grad_norm = np.linalg.norm(grad)
        if mask is not None:
            grad_masked = grad[~mask]
        else:
            grad_masked = grad
        grad_norm_masked = np.linalg.norm(grad_masked)
        displayln_info(verbose_level, f"fcn={fcn:.5E} grad_norm={grad_norm:.5E} grad_norm_masked={grad_norm_masked:.5E}")
        energies = param_arr[all_energies_mask]
        grad_energies = grad[all_energies_mask]
        grad_energies_norm = np.linalg.norm(grad_energies)
        eg_arr = np.stack([ energies, grad_energies, ]).T
        important_eg_arr = eg_arr[abs(grad_energies) > grad_energies_norm / 10]
        displayln_info(verbose_level, f"energies and grad arr=\n{important_eg_arr}")
    #
    def rand_update(param_arr, rng):
        param_arr = param_arr.copy()
        param_arr[rand_update_mask] = (
                param_arr[rand_update_mask]
                + (rng.u_rand_arr(n_params)[rand_update_mask] - 0.5) * r_amp)
        return param_arr
    #
    param_arr_mini = param_arr_initial.copy()
    display_param_arr(param_arr_mini, fcn=fcn_avg, mask=fixed_energies_mask, verbose_level=0)
    #
    rng = RngState(f"fit_energy_amplitude-seed-param")
    #
    displayln_info(0, f"{fname}: mini with fixed all energies")
    for i in range(n_step_mini_avg):
        param_arr_mini = rand_update(param_arr_mini, rng)
        param_arr_mini = minimize_scipy(fcn_avg, param_arr=param_arr_mini,
                                        fixed_param_mask=all_energies_mask,
                                        minimize_kwargs=minimize_kwargs)
        vl = 1
        if i == n_step_mini_avg - 1:
            vl = 0
        display_param_arr(param_arr_mini, fcn=fcn_avg, mask=all_energies_mask, verbose_level=vl)
    #
    displayln_info(0, f"{fname}: mini with fixed some energies")
    for i in range(n_step_mini_avg):
        param_arr_mini = rand_update(param_arr_mini, rng)
        param_arr_mini = minimize_scipy(fcn_avg, param_arr=param_arr_mini,
                                        fixed_param_mask=fixed_energies_mask,
                                        minimize_kwargs=minimize_kwargs)
        displayln_info(0, f"free_energy_arr={param_arr_mini[n_fixed_energies:n_energies]}")
        vl = 1
        if i == n_step_mini_avg - 1:
            vl = 0
        display_param_arr(param_arr_mini, fcn=fcn_avg, mask=fixed_energies_mask, verbose_level=vl)
    #
    def mk_kwargs(jk_idx):
        kwargs = dict(
                jk_idx=jk_idx,
                corr_data=jk_corr_data[jk_idx],
                corr_data_err=corr_data_err,
                t_start_fcn_arr=t_start_fcn_arr,
                param_arr_mini=param_arr_mini,
                n_step_mini_jk=n_step_mini_jk,
                r_amp=r_amp,
                rand_update_mask=rand_update_mask,
                all_energies_mask=all_energies_mask,
                fixed_energies_mask=fixed_energies_mask,
                minimize_kwargs=minimize_kwargs,
                )
        return kwargs
    #
    displayln_info(0, f"{fname}: mini all jk samples")
    mp_map_print_interval = mp_pool_n_proc
    #
    jk_chisq = []
    jk_chisq_grad = []
    jk_param_arr = []
    for idx, v in enumerate(mp_map(jk_mini_task_in_fit_energy_amplitude,
                                   map(mk_kwargs, range(n_jk)))):
        if idx % mp_map_print_interval == 0:
            if n_step_mini_jk != 0:
                displayln_info(0, f"map: {idx}")
        chisq, chisq_grad, param_arr = v
        jk_chisq.append(chisq)
        jk_chisq_grad.append(chisq_grad)
        jk_param_arr.append(param_arr)
    if is_close_pool:
        mp_pool.close()
    #
    jk_chisq = np.array(jk_chisq, dtype=np.float64)
    jk_chisq_grad = np.array(jk_chisq_grad, dtype=np.float64)
    jk_param_arr = np.array(jk_param_arr, dtype=np.float64)
    #
    jk_param_arr_for_scaled_corr = jk_param_arr.copy()
    jk_e_arr = jk_param_arr[:, :n_energies].copy()
    jk_c_arr = jk_param_arr[:, n_energies:].reshape(n_jk, n_energies, n_ops,).copy()
    jk_c_arr = jk_c_arr / op_norm_fac / np.exp(-jk_e_arr[:, :, None] * (t_start_fit - t_start_fcn_arr[None, :, None]) / 2)
    jk_param_arr[:, :n_energies] = jk_e_arr
    jk_param_arr[:, n_energies:] = jk_c_arr.reshape(n_jk, n_energies * n_ops)
    #
    res = dict()
    res['jk_chisq'] = jk_chisq
    res['jk_chisq_grad'] = jk_chisq_grad
    res['jk_param_arr_for_scaled_corr'] = jk_param_arr_for_scaled_corr
    res['jk_param_arr'] = jk_param_arr
    #
    displayln_info(0, f"{fname} finished")
    return res

### -------------------

@timer
def param_evolve(param_arr, mom_arr, hmc_mass_arr, dt):
    param_arr += mom_arr / hmc_mass_arr * dt

@timer
def mom_evolve(mom_arr, param_arr, fcn, dt):
    """
    evolve mom_arr and return force
    """
    chisq, param_grad_arr = fcn(param_arr)
    mom_arr -= param_grad_arr * dt
    return param_grad_arr

@timer
def hmc_energy(param_arr, mom_arr, hmc_mass_arr, fcn):
    return np.sum(mom_arr * mom_arr / hmc_mass_arr) / 2 + fcn(param_arr)[0]

class HmcParams:

    def __init__(
            self,
            *,
            traj=0,
            tau=1.0,
            n_step=32,
            n_params=None,
            param_arr=None,
            hmc_mass_arr=None,
            hmc_mass_adaptive_rate=1/8,
            force_sqr_avg=None,
            delta_hh_history=None,
            temperature=1.0,
            rng=None,
            ):
        """
        Need at least n_params or param_arr
        #
        tau is the MD time
        n_params=len(param_arr)
        Ideally:
        omega = np.pi / 2
        <p^2> == hmc_mass_arr
        omega^2 <p^2> == <F^2> === force_sqr_avg
        Therefore:
        hmc_mass_arr == (4/np.pi**2) * force_sqr_avg
        In case of roughly constant force:
        t = 1
        m = 4/pi^2 * <F^2>
        m ~ 4/pi^2 * F^2
        <p^2> = m
        <v^2> = <p^2> / m^2 = 1 / m ~ pi^2/4 / F^2
        F v t ~ F / sqrt(m) = pi/2
        F a t^2/2 = F^2 / m / 2 ~ pi^2/8
        """
        if rng is None:
            rng = RngState(f"seed-hmc-core-{traj}")
        if param_arr is None:
            assert n_params is not None
            n_params = n_energies * (n_ops + 1)
            param_arr = np.zeros(n_params, dtype=float)
        else:
            if n_params is None:
                n_params = len(param_arr)
            else:
                assert n_params == len(param_arr)
            param_arr = np.array(param_arr, dtype=float)
        if hmc_mass_arr is None:
            hmc_mass_arr = np.ones(n_params, dtype=float)
        elif isinstance(hmc_mass_arr, (int, float)):
            hmc_mass_arr = hmc_mass_arr * np.ones(n_params, dtype=float)
        else:
            hmc_mass_arr = np.array(hmc_mass_arr, dtype=float)
            assert hmc_mass_arr.shape == param_arr.shape
        if delta_hh_history is None:
            delta_hh_history = []
        self.traj = traj
        self.tau = tau
        self.n_step = n_step
        self.n_params = n_params
        self.param_arr = param_arr
        self.hmc_mass_arr = hmc_mass_arr
        self.hmc_mass_adaptive_rate = hmc_mass_adaptive_rate
        self.force_sqr_avg = force_sqr_avg
        self.delta_hh_history = delta_hh_history
        self.temperature = temperature
        self.rng = rng

    def copy(self):
        import copy
        return copy.deepcopy(self)

### -----------------

@timer
def hmc_traj(fcn, hmc_params):
    """
    fcn(param_arr) => chisq, param_grad_arr
    hmc_params is instance of HmcParams
    hmc_params will be modified
    include traj, param_arr, hmc_mass_arr, force_sqr_avg, delta_hh_history
    #
    hmc_mass_adaptive_rate:
    hmc_mass_arr = (1-adaptive_rate) * hmc_mass_arr + hmc_mass_adaptive_rate * (4/np.pi**2) * force_sqr_avg
    """
    fname = get_fname()
    traj = hmc_params.traj
    param_arr = hmc_params.param_arr.copy()
    hmc_mass_arr = hmc_params.hmc_mass_arr
    force_sqr_avg = 0
    delta_hh_history = hmc_params.delta_hh_history
    mom_arr = hmc_params.rng.g_rand_arr(hmc_params.n_params) * np.sqrt(hmc_mass_arr) * np.sqrt(hmc_params.temperature)
    dt = hmc_params.tau / hmc_params.n_step
    hmc_energy_initial = hmc_energy(param_arr, mom_arr, hmc_mass_arr, fcn)
    param_evolve(param_arr, mom_arr, hmc_mass_arr, dt / 2)
    for i in range(hmc_params.n_step):
        force = mom_evolve(mom_arr, param_arr, fcn, dt)
        force_sqr = force * force
        force_sqr_avg = force_sqr_avg + force_sqr
        if i != hmc_params.n_step - 1:
            param_evolve(param_arr, mom_arr, hmc_mass_arr, dt)
        else:
            param_evolve(param_arr, mom_arr, hmc_mass_arr, dt / 2)
        if np.any(np.isnan(param_arr)):
            displayln_info(-1, f"WARNING: {fname} traj={traj} nan encountered. Abort current evolution. Keep hmc_params.param_arr unchanged. (only change traj and delta_hh_history)")
            hmc_params.traj = traj + 1
            delta_hh = np.inf
            delta_hh_history.append(delta_hh)
            return
    force_sqr_avg = force_sqr_avg / hmc_params.n_step
    hmc_energy_final = hmc_energy(param_arr, mom_arr, hmc_mass_arr, fcn)
    delta_hh = hmc_energy_final - hmc_energy_initial
    delta_hh_history.append(delta_hh)
    if hmc_params.hmc_mass_adaptive_rate != 0:
        # Adaptive update hmc_mass_arr
        hmc_mass_arr = (
                (1 - hmc_params.hmc_mass_adaptive_rate) * hmc_mass_arr
                + hmc_params.hmc_mass_adaptive_rate * (4/np.pi**2) * force_sqr_avg)
    displayln_info(0, f"Delta H = {delta_hh} ; H_final={hmc_energy_final} ; H_initial={hmc_energy_initial}")
    if delta_hh > 1e4 * hmc_params.temperature:
        displayln_info(-1, f"WARNING: {fname} traj={traj} Delta H = {delta_hh} too large. Keep hmc_params.param_arr unchanged. (only change traj and delta_hh_history)")
        hmc_params.traj = traj + 1
        delta_hh_history.append(delta_hh)
        return
    elif delta_hh > 10 * hmc_params.temperature:
        displayln_info(-1, f"WARNING: {fname} traj={traj} Delta H = {delta_hh} too large.")
    hmc_params.traj = traj + 1
    hmc_params.param_arr = param_arr
    hmc_params.hmc_mass_arr = hmc_mass_arr
    hmc_params.force_sqr_avg = force_sqr_avg
    hmc_params.delta_hh_history = delta_hh_history

