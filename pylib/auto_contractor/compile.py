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

from auto_contractor.wick import *

from itertools import permutations

class Var(Op):

    def __init__(self, name : str):
        Op.__init__(self, "Var")
        self.name = name

    def __repr__(self):
        return f"{self.otype}({self.name!r})"

    def list(self):
        return [self.otype, self.name]

    def __eq__(self, other) -> bool:
        return self.list() == other.list()

###

def add_positions(s, x):
    if isinstance(x, Term):
        for op in x.c_ops:
            add_positions(s, op)
        for op in x.a_ops:
            add_positions(s, op)
    elif isinstance(x, Op):
        if x.otype == "S":
            s.update([x.p1, x.p2])
        elif x.otype == "Tr":
            for op in x.ops:
                add_positions(s, op)
        elif x.otype == "Qfield":
            s.add(x.p)
    elif isinstance(x, Expr):
        for t in x.terms:
            add_positions(s, t)

def get_positions(term):
    s = set()
    add_positions(s, term)
    return sorted(list(s))

def collect_op_in_cexpr(variables, named_terms):
    var_counter = 0
    var_dataset = {} # var_dataset[op_repr] = op_var
    var_nameset = set()
    for name, value in variables:
        var_nameset.add(name)
    def add_prop_variables(x):
        nonlocal var_counter
        if isinstance(x, list):
            for i, op in enumerate(x):
                if op.otype in ["S",]:
                    op_repr = repr(op)
                    if op_repr in var_dataset:
                        x[i] = var_dataset[op_repr]
                    else:
                        while True:
                            var_counter += 1
                            name = f"V0_{var_counter}"
                            if name not in var_nameset:
                                break
                        variables.append((name, op,))
                        var = Var(name)
                        x[i] = var
                        var_dataset[op_repr] = var
                        var_nameset.add(name)
                elif op.otype == "Tr":
                    add_prop_variables(op.ops)
        elif isinstance(x, Term):
            add_prop_variables(x.c_ops)
        elif isinstance(x, Expr):
            for t in x.terms:
                add_prop_variables(t)
    for name, term in named_terms:
        add_prop_variables(term)
        term.sort()

def find_common_subexpr_in_tr(variables_trs):
    subexpr_count = {}
    def add(x, count_added):
        op_repr = repr(x)
        if op_repr in subexpr_count:
            c, op = subexpr_count[op_repr]
            assert x == op
            subexpr_count[op_repr] = (c + count_added, x)
        else:
            subexpr_count[op_repr] = (1, x)
    def find(x):
        if isinstance(x, list):
            # need to represent the product of the list of operators
            for op in x:
                find(op)
            if len(x) < 2:
                return None
            for i, op in enumerate(x):
                if isinstance(op, Op) and op.otype in [ "Var", "S", "G", ]:
                    op1 = x[(i+1) % len(x)]
                    if isinstance(op1, Op) and op1.otype in [ "Var", "S", "G", ]:
                        prod = [op, op1]
                        if op.otype == "G" and op1.otype == "G":
                            add(prod, 1.02)
                        elif op.otype == "G" or op1.otype == "G":
                            add(prod, 1.01)
                        else:
                            add(prod, 1)
        elif isinstance(x, Op) and x.otype == "Tr" and len(x.ops) >= 2:
            find(x.ops)
        elif isinstance(x, Term):
            find(x.c_ops)
        elif isinstance(x, Expr):
            for t in x.terms:
                find(t)
    for name, tr in variables_trs:
        find(tr)
    max_num_repeat = 1
    best_match = None
    for num_repeat, op in subexpr_count.values():
        if num_repeat > max_num_repeat:
            max_num_repeat = num_repeat
            best_match = op
    return best_match

def collect_common_subexpr_in_tr(variables_trs, op_common, var):
    op_repr = repr(op_common)
    def replace(x):
        if x is None:
            return None
        elif isinstance(x, list):
            # need to represent the product of the list of operators
            for op in x:
                replace(op)
            if len(x) < 2:
                return None
            for i, op in enumerate(x):
                if isinstance(op, Op) and op.otype in ["Var", "S", "G",]:
                    i1 = (i+1) % len(x)
                    op1 = x[i1]
                    if isinstance(op1, Op) and op1.otype in ["Var", "S", "G",]:
                        prod = [op, op1]
                        if repr(prod) == op_repr:
                            x[i1] = None
                            x[i] = var
        elif isinstance(x, Op) and x.otype == "Tr" and len(x.ops) >= 2:
            replace(x.ops)
        elif isinstance(x, Term):
            replace(x.c_ops)
        elif isinstance(x, Expr):
            for t in x.terms:
                replace(t)
    def remove_none(x):
        # return a None removed x
        # possibly modify in-place
        if isinstance(x, list):
            return [ remove_none(op) for op in x if op is not None ]
        elif isinstance(x, Op):
            if x.otype == "Tr":
                x.ops = remove_none(x.ops)
            return x
        elif isinstance(x, Term):
            x.c_ops = remove_none(x.c_ops)
            x.a_ops = remove_none(x.a_ops)
            return x
        elif isinstance(x, Expr):
            x.terms = [ remove_none(t) for t in x.terms]
            return x
        else:
            assert False
    for name, tr in variables_trs:
        replace(tr)
        remove_none(tr)

def collect_subexpr_in_cexpr(variables, named_terms):
    var_nameset = set()
    for name, value in variables:
        var_nameset.add(name)
    variables_trs = []
    var_counter_tr = 0
    var_dataset_tr = {} # var_dataset[op_repr] = op_var
    def add_tr_varibles(x):
        nonlocal var_counter_tr
        if isinstance(x, Term):
            add_tr_varibles(x.c_ops)
        elif isinstance(x, Op) and x.otype == "Tr":
            add_tr_varibles(x.ops)
        elif isinstance(x, list):
            for op in x:
                add_tr_varibles(op)
            for i, op in enumerate(x):
                if isinstance(op, Op) and op.otype == "Tr":
                    op_repr = repr(op)
                    if op_repr in var_dataset_tr:
                        x[i] = var_dataset_tr[op_repr]
                    else:
                        while True:
                            var_counter_tr += 1
                            name = f"V2_{var_counter_tr}"
                            if name not in var_nameset:
                                break
                        variables_trs.append((name, op,))
                        var = Var(name)
                        x[i] = var
                        var_dataset_tr[op_repr] = var
                        var_nameset.add(name)
    for name, term in named_terms:
        add_tr_varibles(term)
        term.sort()
    var_counter = 0
    while True:
        op = find_common_subexpr_in_tr(variables_trs)
        if op is None:
            break
        while True:
            var_counter += 1
            name = f"V1_{var_counter}"
            if name not in var_nameset:
                break
        variables.append((name, op,))
        var = Var(name)
        collect_common_subexpr_in_tr(variables_trs, op, var)
    variables += variables_trs

class CExpr:

    # self.diagram_types
    # self.variables
    # self.named_terms
    # self.named_typed_exprs
    # self.named_exprs
    # self.positions

    def __init__(self, diagram_types, variables, named_terms, named_typed_exprs, named_exprs, positions = None):
        self.diagram_types = diagram_types
        self.variables = variables
        self.named_terms = named_terms
        # typed_expr and expr are a collection of term names representing the sum of these terms
        self.named_typed_exprs = named_typed_exprs
        self.named_exprs = named_exprs
        if positions is not None:
            self.positions = positions
        else:
            s = set()
            for name, term in named_terms:
                add_positions(s, term)
            self.positions = sorted(list(s))

    def __repr__(self) -> str:
        return f"CExpr({self.diagram_types},{self.variables},{self.named_terms},{self.named_typed_exprs},{self.named_exprs},{self.positions})"

    def collect_op(self):
        # Performing common sub-expression elimination
        # Should be called after contract_simplify_compile(*exprs) or mk_cexpr(*exprs)
        # interface function
        # eval term factor
        for name, term in self.named_terms:
            eval_term_factor(term)
        for name, expr in self.named_typed_exprs + self.named_exprs:
            for i in range(len(expr)):
                expr[i] = (complex(expr[i][0]), expr[i][1],)
        # collect prop expr into variables
        collect_op_in_cexpr(self.variables, self.named_terms)
        # collect common subexpr into variables
        collect_subexpr_in_cexpr(self.variables, self.named_terms)

###

def inc(type_dict, key):
    if key in type_dict:
        type_dict[key] += 1
    else:
        type_dict[key] = 1

def drop_tag_last_subscript(tag):
    return tag.rsplit("_", 1)[0]

def mk_permuting_dicts(pos_list):
    for p_pos_list in permutations(pos_list):
        yield dict(zip(pos_list, p_pos_list))

def get_position_permutation_groups(term):
    pos_list = get_positions(term)
    group_dict = dict()
    for pos in pos_list:
        g_pos = drop_tag_last_subscript(pos)
        if g_pos != pos:
            if g_pos not in group_dict:
                group_dict[g_pos] = [ pos, ]
            else:
                group_dict[g_pos].append(pos)
    return group_dict.values()

def mk_combined_permuting_dicts(term):
    pos_list_list = list(get_position_permutation_groups(term))
    p_dicts_list = [ list(mk_permuting_dicts(pos_list)) for pos_list in pos_list_list ]
    def loop(level):
        if level < 0:
            yield dict()
        else:
            for d1 in loop(level - 1):
                for d2 in p_dicts_list[level]:
                    d = d1.copy()
                    d.update(d2)
                    yield d
    return loop(len(p_dicts_list) - 1)

def loop_term_ops(type_dict, ops):
    for op in ops:
        if op.otype == "S":
            # diagram type elem definition
            inc(type_dict, (op.p1, op.p2,))
        elif op.otype == "Tr":
            loop_term_ops(type_dict, op.ops)

def get_term_diagram_type_info_no_permutation(term):
    type_dict = dict()
    loop_term_ops(type_dict, term.c_ops)
    return tuple(sorted(type_dict.items()))

def permute_tag(x, p_dict):
    if x in p_dict:
        return p_dict[x]
    else:
        return x

def permute_type_info_entry(x, p_dict):
    ((p1, p2,), n,) = x
    p1 = permute_tag(p1, p_dict)
    p2 = permute_tag(p2, p_dict)
    return ((p1, p2,), n,)

def permute_type_info(type_info, p_dict):
    l = [ permute_type_info_entry(e, p_dict) for e in type_info ]
    return tuple(sorted(l))

def get_term_diagram_type_info(term):
    base_type_info = get_term_diagram_type_info_no_permutation(term)
    min_type_info = base_type_info
    min_type_info_repr = str(min_type_info)
    for p_dict in mk_combined_permuting_dicts(term):
        type_info = permute_type_info(base_type_info, p_dict)
        type_info_repr = repr(type_info)
        if min_type_info is None or type_info_repr < min_type_info_repr:
            min_type_info = type_info
            min_type_info_repr = type_info_repr
    return min_type_info

def eval_term_factor(term):
    term.coef = complex(term.coef)

def mk_cexpr(*exprs, diagram_type_dict = None):
    # exprs already finished wick contraction,
    # otherwise use contract_simplify_compile(*exprs, is_isospin_symmetric_limit, diagram_type_dict)
    # !!!if diagram_type_dict[diagram_type] == None: this diagram_type will not be included!!!
    # interface function
    if diagram_type_dict is None:
        diagram_type_dict = dict()
    descriptions = [ expr.show() for expr in exprs ]
    # build diagram_types and term names
    diagram_type_counter = 0
    diagram_type_term_dict = dict() # diagram_type_term_dict[repr_term] = diagram_type_name
    term_name_dict = dict() # term_name_dict[term_name] = term
    term_dict = dict() # term_dict[repr(term)] = term_name
    for expr in exprs:
        for term_coef in expr.terms:
            term = Term(term_coef.c_ops, term_coef.a_ops, 1)
            repr_term = repr(term)
            if repr_term in diagram_type_term_dict:
                continue
            diagram_type = get_term_diagram_type_info(term)
            if diagram_type not in diagram_type_dict:
                diagram_type_counter += 1
                diagram_type_name = f"ADT{diagram_type_counter:0>2}" # ADT is short for "auto diagram type"
                diagram_type_dict[diagram_type] = diagram_type_name
            diagram_type_name = diagram_type_dict[diagram_type]
            diagram_type_term_dict[repr_term] = diagram_type_name
            if diagram_type_name is None:
                continue
            term_name_counter = 0
            while True:
                term_name_counter += 1
                term_name = f"term_{diagram_type_name}_{term_name_counter:0>4}"
                if term_name not in term_name_dict:
                    break
            term_name_dict[term_name] = term
            term_dict[repr_term] = term_name
    # name diagram_types
    diagram_types = []
    for diagram_type, diagram_type_name in diagram_type_dict.items():
        diagram_types.append((diagram_type_name, diagram_type,))
    # name terms
    named_terms = []
    for term_name, term in sorted(term_name_dict.items()):
        named_terms.append((term_name, term,))
    # name exprs
    named_typed_exprs = []
    named_exprs = []
    for i, expr in enumerate(exprs):
        expr_list = []
        typed_expr_list_dict = { name : [] for name, diagram_type in diagram_types }
        for j, term in enumerate(expr.terms):
            coef = term.coef
            term.coef = 1
            repr_term = repr(term)
            diagram_type_name = diagram_type_term_dict[repr_term]
            if diagram_type_name is None:
                continue
            term_name = term_dict[repr_term]
            typed_expr_list_dict[diagram_type_name].append((coef, term_name,))
            expr_list.append((coef, term_name,))
        for diagram_type_name, typed_expr_list in typed_expr_list_dict.items():
            if typed_expr_list:
                named_typed_exprs.append((f"# {descriptions[i]}\ntyped_exprs[{i}]['{diagram_type_name}']", typed_expr_list,))
        named_exprs.append((f"# {descriptions[i]}\nexprs[{i}]", expr_list,))
    variables = []
    return CExpr(diagram_types, variables, named_terms, named_typed_exprs, named_exprs)

def contract_simplify_compile(*exprs, is_isospin_symmetric_limit = True, diagram_type_dict = None):
    # e.g. exprs = [ Qb("u", "x", s, c) * Qv("u", "x", s, c) + "u_bar*u", Qb("s", "x", s, c) * Qv("s", "x", s, c) + "s_bar*s", Qb("c", "x", s, c) * Qv("c", "x", s, c) + "c_bar*c", ]
    # e.g. exprs = [ mk_pi_p("x2", True) * mk_pi_p("x1") + "(pi   * pi)", mk_j5pi_mu("x2", 3) * mk_pi_p("x1") + "(a_pi * pi)", mk_k_p("x2", True)  * mk_k_p("x1")  + "(k    * k )", mk_j5k_mu("x2", 3)  * mk_k_p("x1")  + "(a_k  * k )", ]
    # After this function, call cexpr.collect_op() to perform CSE
    # interface function
    if diagram_type_dict is None:
        diagram_type_dict = dict()
    exprs = list(exprs)
    for i in range(len(exprs)):
        expr = copy.deepcopy(exprs[i])
        expr = contract_expr(expr)
        expr.simplify(is_isospin_symmetric_limit = is_isospin_symmetric_limit)
        exprs[i] = expr
    cexpr = mk_cexpr(*exprs, diagram_type_dict = diagram_type_dict)
    return cexpr

def show_variable_value(value):
    if isinstance(value, list):
        return "*".join(map(show_variable_value, value))
    elif isinstance(value, Var):
        return f"{value.name}"
    elif isinstance(value, G) and value.tag in [0, 1, 2, 3, 5]:
        tag = { 0: "x", 1: "y", 2: "z", 3: "t", 5: "5", }[value.tag]
        return f"gamma_{tag}"
    elif isinstance(value, G):
        return f"gamma({value.tag})"
    elif isinstance(value, S):
        return f"S_{value.f}({value.p1},{value.p2})"
    elif isinstance(value, Tr):
        expr = "*".join(map(show_variable_value, value.ops))
        return f"tr({expr})"
    elif isinstance(value, Term):
        if value.coef == 1:
            return "*".join(map(show_variable_value, value.c_ops + value.a_ops))
        else:
            return "*".join(map(show_variable_value, [ f"({value.coef})", ] + value.c_ops + value.a_ops))
    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], str):
        return f"({value[0]})*{value[1]}"
    else:
        return f"{value}"

def display_cexpr_raw(cexpr : CExpr):
    # return a string
    # interface function
    lines = []
    lines.append(f"Begin CExpr")
    lines.append(f"diagram_type_dict = dict()")
    for name, diagram_type in cexpr.diagram_types:
        lines.append(f"diagram_type_dict[{diagram_type}] = \"{name}\"")
    lines.append(f"Positions: {cexpr.positions}")
    for name, value in cexpr.variables:
        lines.append(f"{name:>20} : {value}")
    for name, term in cexpr.named_terms:
        lines.append(f"{name:>20} : {term}")
    for name, typed_expr in cexpr.named_typed_exprs:
        lines.append(f"{name} :\n  {typed_expr}")
    for name, expr in cexpr.named_exprs:
        lines.append(f"{name} :\n  {expr}")
    lines.append(f"End CExpr")
    return "\n".join(lines)

def display_cexpr(cexpr : CExpr):
    # return a string
    # interface function
    lines = []
    lines.append(f"Begin CExpr")
    lines.append(f"diagram_type_dict = dict()")
    for name, diagram_type in cexpr.diagram_types:
        lines.append(f"diagram_type_dict[{diagram_type}] = {repr(name)}")
    position_vars = ", ".join(cexpr.positions)
    lines.append(f"Positions:\n{position_vars} = {cexpr.positions}")
    for name, value in cexpr.variables:
        lines.append(f"  {show_variable_value(value)} + '{name}',")
        lines.append(f"{name:<20} = {show_variable_value(value)}")
    lines.append(f"terms = [")
    for name, term in cexpr.named_terms:
        lines.append(f"  {show_variable_value(term)}, # {name}")
    lines.append(f"]")
    for name, diagram_type in cexpr.diagram_types:
        if name is not None:
            lines.append(f"coef_{name} = 1")
    for idx, (name, term) in enumerate(cexpr.named_terms):
        name_type = "_".join([ "coef", ] + name.split("_")[1:-1])
        lines.append(f"{name} = {name_type} * terms[{idx}]")
    lines.append(f"typed_exprs = [ dict() for i in range({len(cexpr.named_exprs)}) ]")
    for name, typed_expr in cexpr.named_typed_exprs:
        s = "+".join(map(show_variable_value, typed_expr))
        if s == "":
            s = 0
        lines.append(f"{name} = {s}")
    lines.append(f"exprs = [ None for i in range({len(cexpr.named_exprs)}) ]")
    for name, expr, in cexpr.named_exprs:
        s = "+".join(map(show_variable_value, expr))
        if s == "":
            s = 0
        lines.append(f"{name} = {s}")
    lines.append(f"End CExpr")
    return "\n".join(lines)

if __name__ == "__main__":
    expr = Qb("d", "x1", "s1", "c1") * G(5, "s1", "s2") * Qv("u", "x1", "s2", "c1") * Qb("u", "x2", "s3", "c2") * G(5, "s3", "s4") * Qv("d", "x2", "s4", "c2")
    print(expr)
    expr = simplified(contract_expr(expr))
    print(expr)
    cexpr = mk_cexpr(expr)
    print(cexpr)
    cexpr.collect_op()
    print(cexpr)
    print(display_cexpr(cexpr))
    print(CExpr([('S_1', S('d','x2','x1')), ('S_2', S('u','x1','x2'))],[('T_1', Term([Tr([G(5), Var('S_1'), G(5), Var('S_2')],'sc')],[],(-1+0j)))],['x1', 'x2']))
    expr = Expr([Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(0.16666666666666669+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_207','a_s_208'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(0.16666666666666669+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.08333333333333333-0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.08333333333333333-0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.08333333333333333+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(-0.16666666666666669+0j)), Term([G(5,'a_s_203','a_s_204'), G(5,'a_s_209','a_s_210'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('u','x21','a_s_203','a_c_102'), Qv('u','x21','a_s_204','a_c_102'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(-0.16666666666666669+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.08333333333333333-0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.08333333333333333-0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(-0.16666666666666669+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_207','a_s_208'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('u','x22','a_s_207','a_c_104'), Qv('u','x22','a_s_208','a_c_104'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(-0.16666666666666669+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.08333333333333333+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(0.16666666666666669+0j)), Term([G(5,'a_s_205','a_s_206'), G(5,'a_s_209','a_s_210'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('d','x21','a_s_205','a_c_103'), Qv('d','x21','a_s_206','a_c_103'), Qb('d','x22','a_s_209','a_c_105'), Qv('d','x22','a_s_210','a_c_105'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(0.16666666666666669+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.16666666666666669+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.16666666666666669+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.16666666666666669+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.16666666666666669+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(0.3333333333333334+0j)), Term([G(5,'a_s_211','a_s_212'), G(5,'a_s_213','a_s_214'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('u','x21','a_s_211','a_c_106'), Qv('d','x21','a_s_212','a_c_106'), Qb('d','x22','a_s_213','a_c_107'), Qv('u','x22','a_s_214','a_c_107'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(0.3333333333333334+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_219','a_s_220'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(0.16666666666666669+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_219','a_s_220'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('u','x11','a_s_219','a_c_110'), Qv('u','x11','a_s_220','a_c_110'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(-0.16666666666666669+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_221','a_s_222'), G(5,'a_s_223','a_s_224')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('u','x12','a_s_223','a_c_112'), Qv('u','x12','a_s_224','a_c_112')],(-0.16666666666666669+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_221','a_s_222'), G(5,'a_s_225','a_s_226')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('d','x11','a_s_221','a_c_111'), Qv('d','x11','a_s_222','a_c_111'), Qb('d','x12','a_s_225','a_c_113'), Qv('d','x12','a_s_226','a_c_113')],(0.16666666666666669+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_227','a_s_228'), G(5,'a_s_229','a_s_230')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('d','x11','a_s_227','a_c_114'), Qv('u','x11','a_s_228','a_c_114'), Qb('u','x12','a_s_229','a_c_115'), Qv('d','x12','a_s_230','a_c_115')],(0.3333333333333334+0j)), Term([G(5,'a_s_215','a_s_216'), G(5,'a_s_217','a_s_218'), G(5,'a_s_231','a_s_232'), G(5,'a_s_233','a_s_234')],[Qb('d','x21','a_s_215','a_c_108'), Qv('u','x21','a_s_216','a_c_108'), Qb('u','x22','a_s_217','a_c_109'), Qv('d','x22','a_s_218','a_c_109'), Qb('u','x11','a_s_231','a_c_116'), Qv('d','x11','a_s_232','a_c_116'), Qb('d','x12','a_s_233','a_c_117'), Qv('u','x12','a_s_234','a_c_117')],(0.3333333333333334+0j))])
    cexpr = contract_simplify_compile(expr, is_isospin_symmetric_limit = True)
    print(display_cexpr(cexpr))
    cexpr.collect_op()
    print(display_cexpr(cexpr))
