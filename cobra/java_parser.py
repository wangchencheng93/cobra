#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Project
    ~~~~~

    Project ins

    :author:    BlBana <635373043@qq.com>
    :homepage:  http://drops.blbana.cc
    :license:   MIT, see LICENSE for more details.
    :copyright: Copyright (c) 2018 BlBana. All rights reserved
"""

import sys
import javalang
import logging
from javalang.tree import *
from cobra.log import logger
from cobra.rule import Rule


logger.setLevel(logging.DEBUG)

sys.setrecursionlimit(2000)


class JavaAst(object):
    def __init__(self):
        self.scan_results = []
        self.sources = []
        self.import_package = []
        r = Rule()
        self.sources = r.sources

    # ####################### 分析语法结构 #############################
    def analysis(self, nodes, sink, back_node, vul_lineno):
        """
        解析语法结构，获取语法树内容，含有sink函数的语法由单独模块进行分析
        :param nodes: 语法树
        :param sink: 敏感函数
        :param back_node: 回溯节点
        :param vul_lineno: Sink函数所在行号
        :return:
        """
        for path, node in nodes:
            if isinstance(node, CompilationUnit):
                pass

            elif isinstance(node, ClassDeclaration):
                pass

            elif isinstance(node, MethodDeclaration):
                pass

            elif isinstance(node, FormalParameter):
                pass

            elif isinstance(node, ReferenceType):
                pass

            elif isinstance(node, Import):
                self.analysis_import(node)

            elif isinstance(node, StatementExpression):
                self.analysis_nodes(node, sink, back_node, vul_lineno)

            elif isinstance(node, LocalVariableDeclaration):
                self.analysis_nodes(node, sink, back_node, vul_lineno)

            elif isinstance(node, MethodInvocation):
                pass

            elif isinstance(node, Literal):
                pass

            back_node.append(node)

    def analysis_nodes(self, node, sink, back_node, vul_lineno):
        """
        用于定位不同语法类型的Sink函数位置，并进行参数的提取操作
        :param node:
        :param sink:
        :param back_node:
        :param vul_lineno:
        :return:
        """
        sink_list = sink.split(':')  # ['方法名', '包名']

        if len(sink_list) == 2:
            if isinstance(node, StatementExpression):
                if self.analysis_sink(node.expression, sink_list, vul_lineno):  # 判断是否为Sink函数
                    params = self.analysis_node(node.expression)  # 提取Sink函数的所有参数
                    logger.debug('[Java-AST] [SINK] Sink function param(s): {0}'.format(params))
                    self.start_analysis_params(params, sink, back_node)  # 开始回溯参数的来源

            if isinstance(node, LocalVariableDeclaration):
                if self.analysis_sink(node.declarators, sink_list, vul_lineno):
                    params = self.analysis_node(node)
                    logger.debug('[Java-AST] [SINK] Sink function param(s): {0}'.format(params))
                    self.start_analysis_params(params, sink, back_node)

        else:
            logger.warning('[Java-AST] The sink function list index out of range')

    def analysis_sink(self, node, sink, vul_lineno):
        """
        用于判断node节点中是否存在Sink函数
        :param node:
        :param sink:
        :param vul_lineno:
        :return:
        """
        if isinstance(node, MethodInvocation):
            result = self.analysis_sink_method_invocation(node, sink, vul_lineno)
            return result

        if isinstance(node, Assignment):
            if isinstance(node.value, MethodInvocation):
                result = self.analysis_sink_method_invocation(node.value, sink, vul_lineno)
                return result

        if isinstance(node, list):
            for n in node:
                if isinstance(n, VariableDeclarator):
                    if isinstance(n.initializer, MethodInvocation):
                        result = self.analysis_sink(n.initializer, sink, vul_lineno)
                        return result

        return False

    def analysis_sink_method_invocation(self, node, sink, vul_lineno):
        """
        判断Sink函数是否存在
        :param node:
        :param sink:
        :return:
        """
        qualifier = node.qualifier  # 对象名
        member = node.member  # 方法名
        lineno = self.get_node_lineno(node)

        if int(lineno) == int(vul_lineno) and sink[0] == member and sink[1] in self.import_package:  # 判断方法是否为Sink点
            logger.debug('[Java-AST] Found the sink function --> {q}.{m} in line {l}'.format(q=sink[0], m=sink[1], l=lineno))
            return True

        else:
            return False

    # ####################### 回溯参数传递 #############################
    def start_analysis_params(self, params, sink, back_node):
        """
        用于开始对Sink函数的参数进行回溯，并收集记录回溯结果
        :param params:
        :param sink:
        :param back_node:
        :return:
        """
        try:
            if isinstance(params, list):
                for param in params:
                    logger.debug('[Java-AST] [SINK] Start back param --> {0}'.format(param))
                    is_controllable = self.back_statement_expression(param, back_node)
                    self.set_scan_results(is_controllable, sink)

            else:
                logger.debug('[Java-AST] [SINK] Start back param --> {0}'.format(params))
                is_controllable = self.back_statement_expression(params, back_node)
                self.set_scan_results(is_controllable, sink)
        except RuntimeError:
            logger.debug('Maximum recursion depth exceeded')

    def back_statement_expression(self, param, back_node):
        """
        开始回溯Sink函数参数
        :param param:
        :param back_node:
        :return:
        """
        # is_controllable = self.is_controllable(param)
        is_controllable = -1

        if len(back_node) != 0 and is_controllable == -1:
            node = back_node[len(back_node)-1]
            lineno = self.get_node_lineno(node)

            if isinstance(node, LocalVariableDeclaration):
                node_param = self.get_node_name(node.declarators)  # 获取被赋值变量
                expr_param, sink = self.get_expr_name(node.declarators)  # 取出赋值表达式中的内容

                is_controllable = self.back_node_is_controllable(node_param, param, sink, expr_param, lineno, back_node)

            if isinstance(node, Assignment):
                node_param = self.get_node_name(node.expressionl)
                expr_param, sink = self.get_expr_name(node.value)  # expr_param为方法名, sink为回溯变量

                is_controllable = self.back_node_is_controllable(node_param, param, sink, expr_param, lineno, back_node)

            if isinstance(node, FormalParameter):
                node_param = self.get_node_name(node)  # 获取被赋值变量
                expr_param, sink = self.get_expr_name(node)  # 取出赋值表达式中的内容

                is_controllable = self.back_node_is_controllable(node_param, param, sink, expr_param, lineno, back_node)

            if is_controllable == -1:
                is_controllable = self.back_statement_expression(param, back_node[:-1])

        return is_controllable

    def back_node_is_controllable(self, node_param, param, sink, expr_param, lineno, back_node):
        """
        对回溯的节点进行可控判断，并对多参数的
        :param node_param:
        :param param:
        :param sink:
        :param expr_param:
        :param lineno:
        :param back_node:
        :return:
        """
        is_controllable = -1

        if node_param == param and not isinstance(sink, list):
            logger.debug('[Java-AST] [BACK] analysis sink  {s} --> {t} in line {l}'.format(s=param, t=sink,
                                                                                           l=lineno))
            param = sink
            is_controllable = self.is_controllable(expr_param, lineno)

        if node_param == param and isinstance(sink, list):
            is_controllable = self.is_controllable(expr_param, lineno)

            for s in sink:
                logger.debug('[Java-AST] [BACK] analysis sink  {s} --> {t} in line {l}'.format(s=param, t=s,
                                                                                               l=lineno))
                param = s

                if is_controllable == 1:
                    return is_controllable

                _is_controllable = self.back_statement_expression(param, back_node[:-1])

                if _is_controllable != -1:
                    is_controllable = _is_controllable

        return is_controllable

    # ####################### 分析节点类型 #############################
    def analysis_node(self, node):
        if isinstance(node, MethodInvocation):
            param = self.get_node_arguments(node.arguments)
            return param

        elif isinstance(node, LocalVariableDeclaration):
            param = self.analysis_variable_declaration(node.declarators)
            return param

        elif isinstance(node, Assignment):
            param = self.analysis_assignment(node.value)
            return param

        else:
            logger.debug("[Java-AST] Can't analysis node --> {n} in analysis_node method".format(n=node))
            return ''

    def analysis_variable_declaration(self, nodes):
        for node in nodes:
            if isinstance(node, VariableDeclarator):
                if isinstance(node.initializer, MethodInvocation):
                    params = self.get_method_invocation_params(node.initializer)
                    return params

    def analysis_assignment(self, node):
        if isinstance(node, MethodInvocation):
            param = self.get_method_invocation_params(node)
            return param

        else:
            logger.debug("[Java-AST] Can't analysis node --> {n} in analysis_assignment method".format(n=node))

    def analysis_import(self, node):
        if hasattr(node, 'path'):
            self.import_package.append(node.path)

    # ####################### 提取参数内容 #############################
    def get_node_arguments(self, nodes):
        """
        用于获取node.arguments中的所有参数
        :param nodes:
        :return: list
        """
        params_list = []
        for node in nodes:
            if isinstance(node, MemberReference):
                param = self.get_member_reference_name(node)
                params_list.append(param)

            if isinstance(node, BinaryOperation):
                params = self.get_binary_operation_params(node)
                params_list.append(params)

            if isinstance(node, MethodInvocation):
                params = self.get_method_invocation_params(node)
                params_list.append(params)

        return self.export_list(params_list, [])

    def get_method_invocation_params(self, node):
        params_list = []
        qualifier = self.get_method_object_name(node)
        if qualifier is not '':
            params_list.append(qualifier)

        for argument in node.arguments:
            if isinstance(argument, MethodInvocation):
                params = self.get_method_invocation_params(argument)
                params_list.append(params)

            else:
                if isinstance(argument, MemberReference):
                    params = self.get_member_reference_name(argument)
                    params_list.append(params)

                if isinstance(argument, BinaryOperation):
                    params = self.get_binary_operation_params(argument)
                    params_list.append(params)

                if isinstance(argument, Literal):
                    params = self.get_literal_params(argument)
                    params_list.append(params)

        return self.export_list(params_list, [])

    def get_method_invocation_member(self, node):
        """
        取方法调用的 对象名 + 方法名
        :param node:
        :return:
        """
        qualifier = node.qualifier
        member = node.member
        # result = qualifier + '.' + member
        result = member
        lineno = self.get_node_lineno(node)
        logger.debug('[Java-AST] analysis method --> {r} in line {l}'.format(r=result, l=lineno))
        return result

    @staticmethod
    def get_class_creator_type(node):
        """
        用于获取ClassCreator类型的type类型
        :param node:
        :return:
        """
        if isinstance(node, ReferenceType):
            return node.name

        else:
            return ''

    def get_binary_operation_params(self, node):  # 当为BinaryOp类型时，分别对left和right进行处理，取出需要的变量
        params = []

        if isinstance(node.operandr, MemberReference) or isinstance(node.operandl, MemberReference):
            if isinstance(node.operandr, MemberReference):
                param = self.get_member_reference_name(node.operandr)
                params.append(param)

            if isinstance(node.operandl, MemberReference):
                param = self.get_member_reference_name(node.operandl)
                params.append(param)

        if not isinstance(node.operandr, MemberReference) or not isinstance(node.operandl, MemberReference):
            param_right = self.get_deep_binary_operation_params(node.operandr)
            param_left = self.get_deep_binary_operation_params(node.operandl)

            params = list(param_right) + list(param_left) + list(params)

        params = self.export_list(params, [])
        return params

    def get_deep_binary_operation_params(self, node):
        param = []

        if isinstance(node, BinaryOperation):
            param = self.get_binary_operation_params(node)

        if isinstance(node, MethodInvocation):
            param = self.get_method_invocation_params(node)

        return param

    def get_annotations_name(self, nodes):
        """
        提取Spring框架中annotations的类型
        :param nodes:
        :return:
        """
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, Annotation):
                    return node.name

    def get_method_object_name(self, node):
        """
        提取调用方法的实例化对象的变量名
        :param node:
        :return:
        """
        return node.qualifier

    def get_member_reference_name(self, node):
        """
        提取MemberReference语法中的参数
        :param node: MemberReference语法节点
        :return: 返回提取的参数变量
        """
        return node.member

    def get_literal_params(self, node):
        """
        取Literal常亮的值
        :param node:
        :return:
        """
        return node.value

    def get_node_name(self, nodes):
        """
        node回溯节点-->提取被复制变量名
        :param node:
        :return:
        """
        param_node = ''
        try:
            if isinstance(nodes, list):  # 取出LocalVariableDeclaration结构的变量名
                for node in nodes:
                    if isinstance(node, VariableDeclarator):
                        param_node = node.name

            if isinstance(nodes, MemberReference):  # 取出Assinment结构的变量名
                param_node = self.get_member_reference_name(nodes)

            if isinstance(nodes, FormalParameter):  # 取出Spring框架注解的入参
                param_node = nodes.name

        except IndexError as e:
            logger.warning(e.message)

        return param_node

    def get_expr_name(self, nodes):
        """
        用来获取表达式节点信息
        :param node:
        :return:  expr_node(用于判断是否可控)，sink(用于跟踪参数传递)
        """
        expr_param = ''
        sink = ''

        if isinstance(nodes, MethodInvocation):  # 当赋值表达式为方法调用
            sink = self.get_method_invocation_params(nodes)
            expr_param = self.get_method_invocation_member(nodes)
            return expr_param, sink

        if isinstance(nodes, ClassCreator):
            sink = self.get_node_arguments(nodes.arguments)
            expr_param = self.get_class_creator_type(nodes.type)
            return expr_param, sink

        elif isinstance(nodes, FormalParameter):  # 取出Spring框架注解类型 和 参数
            sink = nodes.name
            expr_param = self.get_annotations_name(nodes.annotations)
            return expr_param, sink

        elif isinstance(nodes, list):
            for node in nodes:
                if isinstance(node.initializer, MethodInvocation):
                    sink = self.get_method_invocation_params(node.initializer)
                    expr_param = self.get_method_invocation_member(node.initializer)
                    return expr_param, sink

                if isinstance(node.initializer, ClassCreator):
                    sink = self.get_node_arguments(node.initializer.arguments)
                    expr_param = self.get_class_creator_type(node.initializer.type)
                    return expr_param, sink

                else:
                    logger.debug("Can't analysis node --> {} in get_expr_name method".format(node))
                    return expr_param, sink

        else:
            logger.debug("Can't analysis node --> {} in get_expr_name method".format(nodes))
            return expr_param, sink

    def get_node_lineno(self, node):
        lineno = 0

        if hasattr(node, '_position'):
            lineno = node._position[0]

        elif isinstance(node, Assignment):
            if isinstance(node.value, MethodInvocation):
                lineno = node.value._position[0]

        elif isinstance(node, StatementExpression):
            lineno = self.get_node_lineno(node.expression)

        elif isinstance(node, VariableDeclarator):
            lineno = self.get_node_lineno(node.initializer)

        return lineno

    # ####################### 分析语法结构 #############################
    def is_controllable(self, expr, lineno=0):
        """
        用于判断是否调用了外部传参
        :param expr:
        :param lineno:
        :return:
        """
        for key in self.sources:
            if str(expr) in self.sources[key]:
                if key in self.import_package:
                    logger.debug('[Java-AST] Found the source function --> {e} in line {l}'.format(e=expr,
                                                                                                   l=lineno))
                    return 1
        return -1

    # ####################### 保存扫描结果 #############################
    def set_scan_results(self, is_controllable, sink):
        result = {
            'code': is_controllable,
            'sink': sink
        }

        if result['code'] != -1:
            self.scan_results.append(result)

    # ####################### 保存扫描结果 #############################
    def export_list(self, params, export_params):
        """
        将params中嵌套的多个列表，导出为一个列表
        :param params:
        :param export_params:
        :return:
        """
        for param in params:
            if isinstance(param, list):
                export_params = self.export_list(param, export_params)

            else:
                export_params.append(param)

        return export_params


def java_scan_parser(code_content, sensitive_func, vul_lineno):
    back_node = []
    tree = javalang.parse.parse(code_content)
    java_ast = JavaAst()
    for sink in sensitive_func:
        java_ast.analysis(tree, sink, back_node, vul_lineno)
    return java_ast.scan_results
