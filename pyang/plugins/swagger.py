"""Swagger output plugin for pyang.

    List of contributors:
    -Sebastiano Miano, Computer Networks Group (Netgorup), Politecnico di Torino
    [sebastiano.miano@polito.it]
    -Arturo Mayoral, Optical Networks & Systems group, Centre Tecnologic de Telecomunicacions de Catalunya (CTTC).
    [arturo.mayoral@cttc.es]
    -Ricard Vilalta, Optical Networks & Systems group, Centre Tecnologic de Telecomunicacions de Catalunya (CTTC)
    [ricard.vilalta@cttc.es]

    -Description:
    This code  implements a pyang plugin to translate yang RFC-6020 model files into swagger 2.0 specification
    json format (https://github.com/swagger-api/swagger-spec).
    Any doubt, bug or suggestion: arturo.mayoral@cttc.es
"""

import optparse
import json
import os
import re
import yaml
import string
from collections import OrderedDict
import copy

from pyang import plugin
from pyang import statements
from pyang import error
from pyang import types

TYPEDEFS = dict()
PARENT_MODELS = dict()


def pyang_plugin_init():
    """ Initialization function called by the plugin loader. """
    plugin.register_plugin(SwaggerPlugin())


class SwaggerPlugin(plugin.PyangPlugin):
    """ Plugin class for swagger file generation."""
    git_info = ""

    def add_output_format(self, fmts):
        self.multiple_modules = True
        fmts['swagger'] = self

    def add_opts(self, optparser):
        # A list of command line options supported by the swagger plugin.
        # TODO: which options are really needed?
        optlist = [
            optparse.make_option(
                '--swagger-help',
                dest='swagger_help',
                action='store_true',
                help='Print help on swagger options and exit'),
            optparse.make_option(
                '--swagger-start-name',
                type='string',
                dest='swagger_start_name',
                help='Name of the base path to print'),
            optparse.make_option(
                '--simplify-api',
                default=False,
                dest='s_api',
                help='Simplified apis'),
            optparse.make_option(
                '--swagger-path',
                dest='swagger_path',
                type='string',
                help='Path to print'),
            optparse.make_option(
                '--swagger-base-path',
                dest='swagger_base_path',
                type='string',
                help='Base path to add'),
            optparse.make_option(
                '--restconf-path',
                dest='is_restconf_path',
                action='store_true',
                help='Flag indicating if the base path is a restconf path'),
            optparse.make_option(
                '--all-restconf-methods',
                dest = 'generate_all_restconf_methods',
                action = 'store_true',
                help = 'If flag set to true, methods OPTIONS and HEAD are generated')]
        optgrp = optparser.add_option_group('Swagger specific options')
        optgrp.add_options(optlist)

    def setup_ctx(self, ctx):
        self.read_yaml_config_file(ctx)
        pass

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def pre_validate(self, ctx, modules):
        for module in modules:
            add_fake_list_at_beginning(module)

    def emit(self, ctx, modules, fd):
        # TODO: the path variable is currently not used.
        if ctx.opts.swagger_path is not None:
            path = string.split(ctx.opts.swagger_path, '/')
            if path[0] == '':
                path = path[1:]
        else:
            path = None

        global S_API
        S_API = ctx.opts.s_api
        emit_swagger_spec(ctx, modules, fd, ctx.opts.path, self.git_info)

    def read_yaml_config_file(self, ctx):
        path = "/.config/iovnet/pyang-swagger.yaml"
        home = os.environ['HOME']
        if not home:
            return

        path = home + path

        if not os.path.exists(path):
            print("No configuration file found in " + path)
            print("Use the install.sh script under pyang-swagger")
            print("Proceed with default config...")
            return

        with open(path, 'r') as stream:
            try:
                data_loaded = yaml.load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                return

        if 'git-info' in data_loaded and data_loaded['git-info']:
            self.git_info = data_loaded['git-info']


def add_top_list_parameters(top_list, old_list, leaf_name, leaf_name_keyword, module):
    top_list.i_config = True
    top_list.i_is_validated = True
    top_list.i_key = [leaf_name]
    top_list.i_module = module
    top_list.i_origin_module = module
    top_list.i_typedefs = dict()
    top_list.i_unique = list()
    top_list.i_uniques = list()
    top_list.is_grammatically_valid = True

    top_list.i_children = [leaf_name]
    top_list.i_children.extend(old_list)
    top_list.substmts.append(leaf_name_keyword)
    top_list.substmts.append(leaf_name)
    top_list.substmts.extend(old_list)


def add_leaf_name_keyword_parameters(leaf_name_keyword, module):
    leaf_name_keyword.i_groupings = dict()
    leaf_name_keyword.i_module = module
    leaf_name_keyword.i_origin_module = module
    leaf_name_keyword.i_typedefs = dict()
    leaf_name_keyword.i_uniques = list()
    leaf_name_keyword.is_grammatically_valid = True        


def add_fake_list_at_beginning(module):
    top_list = statements.Statement(module, module, error.Position("Automatically inserted statement"), "list", module.arg)

    leaf_name = statements.Statement(module, top_list, error.Position("Automatically inserted statement"), "leaf", "name")

    add_leaf_name_parameters(leaf_name, module)

    leaf_name_keyword = statements.Statement(module, top_list, error.Position("Automatically inserted statement"), "key", "name")
    add_leaf_name_keyword_parameters(leaf_name_keyword, module)

    old_list = list(module.i_children)
    del module.i_children[:]

    add_top_list_parameters(top_list, old_list, leaf_name, leaf_name_keyword, module)

    module.i_children.append(top_list)

    base_child = get_basemodel_grouping_children(module)
    del module.substmts[-len(old_list)+base_child:]
    module.substmts.append(top_list)


def get_basemodel_grouping_children(module):
    modules = module.i_ctx.modules
    for key in modules:
        if isinstance(key, tuple) and key[0] == "base-iovnet-service-model":
            grouping = modules[key].substmts[-1]
            if grouping.arg == 'base-yang-module' and grouping.keyword == 'grouping':
                return len(grouping.i_children)

    return 0


def add_leaf_name_parameters(leaf_name, module):
    leaf_name.i_config = True
    leaf_name.i_default = None
    leaf_name.i_default_str = ""
    leaf_name.i_groupings = dict()
    leaf_name.i_is_key = True
    leaf_name.i_leafref = None
    leaf_name.i_leafref_expanded = False
    leaf_name.i_leafref_ptr = None
    leaf_name.i_module = module
    leaf_name.i_origin_module = module
    leaf_name.i_typedefs = dict()
    leaf_name.i_uniques = list()
    leaf_name.is_grammatically_valid = True

    leaf_name_type = statements.Statement(module, leaf_name, error.Position("Automatically inserted statement"), "type",
                                          "string")
    leaf_name_type.i_groupings = dict()
    leaf_name_type.i_is_derived = False
    leaf_name_type.i_is_validated = True
    leaf_name_type.i_lengths = list()
    leaf_name_type.i_module = module
    leaf_name_type.i_origin_module = module
    leaf_name_type.i_ranges = list()
    leaf_name_type.i_type_spec = types.StringTypeSpec()
    leaf_name_type.i_type_spec.base = None
    leaf_name_type.i_type_spec.definition = ""
    leaf_name_type.i_type_spec.name = "string"
    leaf_name_type.i_typedef = None
    leaf_name_type.i_typedefs = dict()
    leaf_name_type.i_uniques = list()
    leaf_name_type.is_grammatically_valid = True

    leaf_name_mandatory = statements.Statement(module, leaf_name, error.Position("Automatically inserted statement"),
                                               "mandatory", "true")
    leaf_name_mandatory.i_groupings = dict()
    leaf_name_mandatory.i_module = module
    leaf_name_mandatory.i_origin_module = module
    leaf_name_mandatory.i_typedefs = dict()
    leaf_name_mandatory.i_uniques = list()
    leaf_name_mandatory.is_grammatically_valid = True

    leaf_name_description = statements.Statement(module, leaf_name, error.Position("Automatically inserted statement"),
                                                 "description", "Name of the {0} service".format(module.arg))
    leaf_name_description.i_groupings = dict()
    leaf_name_description.i_module = module
    leaf_name_description.i_origin_module = module
    leaf_name_description.i_typedefs = dict()
    leaf_name_description.i_uniques = list()
    leaf_name_description.is_grammatically_valid = True

    leaf_name.substmts.append(leaf_name_type)
    leaf_name.substmts.append(leaf_name_mandatory)
    leaf_name.substmts.append(leaf_name_description)


def print_header(module, fd, children, git_info):
    """ Print the swagger header information."""
    module_name = str(module.arg)

    global _MODULE_NAME
    _MODULE_NAME = module_name

    header = OrderedDict()
    header['swagger'] = '2.0'
    header['info'] = {
        'description': '%s API generated from %s.yang' % (
            module_name, module_name),  # module.pos.ref.rsplit('/')[-1]),
        'version': '1.0.0',
        'title': str(module_name + ' API')
    }
    header['host'] = 'localhost:8080'

    if 'swagger_base_path' in locals():
        header['basePath'] = swagger_base_path
    else:
        header['basePath'] = '/'

    if git_info:
        header['info']['x-pyang-git-info'] = git_info

    if module.pos.ref:
        header['info']['x-yang-path'] = str(module.pos.ref)

    header['schemes'] = ['http']
    for attribute in module.substmts:
        if isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "service-description":
            header['info']['description'] = attribute.arg
        elif isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "service-version":
            header['info']['version'] = attribute.arg
        elif isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "service-name":
            header['info']['x-service-name'] = attribute.arg
        elif isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "service-min-kernel-version":
            if re.match(r"[1-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}", attribute.arg):
                header['info']['x-service-min-kernel-version'] = attribute.arg
            else:
                raise error.EmitError("The parameter service-min-kernel-version doesn't match the patter (e.g. x.y[.z]")

    # Add tags to the header to group the APIs based on every root node found in the YANG
    if len(children) > 0:
        header['tags'] = list(dict())
        for i, child in enumerate(children):
            value = {
                'name': child.arg
                # TODO: Add here additional information for the tag
            }
            header['tags'].append(value.copy())

    return header


def emit_swagger_spec(ctx, modules, fd, path, git_info):
    """ Emits the complete swagger specification for the yang file."""

    printed_header = False
    model = OrderedDict()
    definitions = OrderedDict()

    # Go through all modules and extend the model.
    for module in modules:
        # extract children which contain data definition keywords
        if hasattr(module, "i_children"):
            chs = [ch for ch in module.i_children
                   if ch.keyword in (statements.data_definition_keywords + ['rpc', 'notification'])]

        if not printed_header:
            model = print_header(module, fd, chs, git_info)
            printed_header = True
            path = '/'

        if hasattr(module, "i_typedefs"):
            typdefs = [module.i_typedefs[element] for element in module.i_typedefs]
        if hasattr(module,  "i_groupings"):
            models = list(module.i_groupings.values())
        referenced_types = list()
        referenced_types = find_typedefs(ctx, module, modules, referenced_types)
        for element in referenced_types:
            typdefs.append(element)

        # The attribute definitions are processed and stored in the "typedefs" data structure for further use.
        gen_typedefs(typdefs)

        # list() needed for python 3 compatibility
        referenced_models = list()
        referenced_models = find_models(ctx, module, models, referenced_models)
        # referenced_models.extend(find_models(ctx, module, chs, referenced_models))

        for element in referenced_models:
            models.append(element)

        # Print the swagger definitions of the Yang groupings.
        gen_model(models, definitions)

        # If a model at runtime was dependant of another model which had been encounter yet,
        # it is generated 'a posteriori'.
        if pending_models:
            gen_model(pending_models, definitions)

        if PARENT_MODELS:
            for element in PARENT_MODELS:
                if PARENT_MODELS[element]['models']:
                    definitions[element]['discriminator'] = PARENT_MODELS[element]['discriminator']

        # generate the APIs for all children
        if len(chs) > 0:
            model['paths'] = OrderedDict()
            gen_apis(chs, path, model['paths'], definitions, is_root=True)

        model['definitions'] = definitions
        modulepath = "/{0}/".format(module.arg)
        del model['paths'][modulepath]['put']
        del model['paths'][modulepath]['delete']
        del model['paths'][modulepath]['post']

        # mark methods that have a default implementation
        # service level
        model['paths'][modulepath]['get']['x-has-default-impl'] = True

        # instance level
        model['paths'][modulepath + '{name}/']['post']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/']['delete']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/']['put']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/uuid/']['get']['x-has-default-impl'] = True

        # port list level?
        model['paths'][modulepath + '{name}/ports/']['post']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/']['put']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/']['get']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/']['delete']['x-has-default-impl'] = True

        # ports level
        model['paths'][modulepath + '{name}/ports/{ports_name}/']['post']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/{ports_name}/']['put']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/{ports_name}/']['get']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/{ports_name}/']['delete']['x-has-default-impl'] = True

        # sub-elements in port
        model['paths'][modulepath + '{name}/ports/{ports_name}/peer/']['patch']['x-has-default-impl'] = True
        model['paths'][modulepath + '{name}/ports/{ports_name}/peer/']['get']['x-has-default-impl'] = True

        model['paths'][modulepath + '{name}/ports/{ports_name}/uuid/']['get']['x-has-default-impl'] = True

        model['paths'][modulepath + '{name}/ports/{ports_name}/status/']['get']['x-has-default-impl'] = True
        # model['paths'][modulepath + '{name}/ports/{ports_name}/status/']['patch']['x-has-default-impl'] = True

        fd.write(json.dumps(model, indent=4, separators=(',', ': ')))


def find_models(ctx, module, children, referenced_models):
    for child in children:
        if hasattr(child, 'substmts'):
            for attribute in child.substmts:
                if attribute.keyword == 'uses':
                    if len(attribute.arg.split(':')) > 1:
                        for i in module.search('import'):
                            subm = ctx.get_module(i.arg)
                            models = [group for group in subm.i_groupings.values() if
                                      group.arg not in [element.arg for element in referenced_models]]

                            for element in models:
                                referenced_models.append(element)

                            referenced_models = find_models(ctx, subm, models, referenced_models)
                    else:
                        models = [group for group in module.i_groupings.values() if
                                  group.arg not in [element.arg for element in referenced_models]]
                        for element in models:
                            referenced_models.append(element)

        if hasattr(child, 'i_children'):
            find_models(ctx, module, child.i_children, referenced_models)

    return referenced_models


def find_typedefs(ctx, module, children, referenced_types):
    for child in children:
        if hasattr(child, 'substmts'):
            for attribute in child.substmts:
                if attribute.keyword == 'type':
                    if len(attribute.arg.split(':')) > 1:
                        for i in module.search('import'):
                            subm = ctx.get_module(i.arg)
                            models = [type for type in subm.i_typedefs.values() if
                                      str(type.arg) == str(attribute.arg.split(':')[-1]) and type.arg not in [
                                          element.arg for element in referenced_types]]
                            for element in models:
                                referenced_types.append(element)
                            referenced_types = find_typedefs(ctx, subm, models, referenced_types)
                    else:
                        models = [type for type in module.i_typedefs.values() if
                                  str(type.arg) == str(attribute.arg) and type.arg not in [element.arg for element in
                                                                                           referenced_types]]
                        for element in models:
                            referenced_types.append(element)

        if hasattr(child, 'i_children'):
            find_typedefs(ctx, module, child.i_children, referenced_types)
    return referenced_types


pending_models = list()


def distinguish_attribute_type(attribute, node):
    if len(attribute.arg.split(':')) > 1:
        attribute.arg = attribute.arg.split(':')[-1]
    # Firstly, it is checked if the attribute type has been previously define in typedefs.
    if hasattr(attribute, 'i_typedef') and attribute.i_typedef:
        set_node_type_info(attribute.i_typedef, node)

    if attribute.arg in TYPEDEFS:
        if TYPEDEFS[attribute.arg]['type'][:3] == 'int':
            node['type'] = 'integer'
            node['format'] = TYPEDEFS[attribute.arg]['format']
        elif TYPEDEFS[attribute.arg]['type'] == 'enumeration':
            node['type'] = 'string'
            node['x-typedef'] = TYPEDEFS[attribute.arg]['name']
            node['enum'] = [e for e in TYPEDEFS[attribute.arg]['enum']]
        # map all other types to string
        else:
            node['type'] = 'string'
    elif attribute.arg[:-2] == 'int' or attribute.arg[:-2] == 'uint' or attribute.arg[:-1] == 'int' or attribute.arg[:-1] == 'uint': # added this check in order to consider int8 e uint8
        node['type'] = 'integer'
        node['format'] = attribute.arg
    elif attribute.arg == 'decimal64':
        node['type'] = 'number'
        node['format'] = 'double'
    elif attribute.arg == 'boolean':
        node['type'] = attribute.arg
    elif attribute.arg == 'enumeration':
        node['type'] = 'string'
        node['enum'] = [e[0] for e in attribute.i_type_spec.enums]
    elif attribute.arg == 'leafref':
        node['type'] = 'string'
        node['x-path'] = attribute.i_type_spec.path_.arg
    # map all other types to string
    else:
        node['type'] = 'string'


def set_node_type_info(typedef, node):
    if hasattr(typedef, "substmts"):
        for elem in typedef.substmts:
            if elem.keyword == 'type' and hasattr(elem, "substmts") and elem.substmts:
                for nested_elem in elem.substmts:
                    if nested_elem.keyword == 'pattern':
                        node['format'] = str(nested_elem.arg)
                        node['type'] = str(elem.arg)
                    elif nested_elem.keyword == 'range':
                        minimum, maximum = str(nested_elem.arg).split("..")
                        node['format'] = str(elem.arg)
                        node['minimum'] = int(minimum)
                        node['maximum'] = int(maximum)


def gen_model(children, tree_structure, config=True, definitions=None):
    """ Generates the swagger definition tree."""
    for child in children:
        referenced = False
        node = dict()
        nonRefChildren = None
        listkey = None
        required_elem_list = list()

        if hasattr(child, 'substmts'):
            for attribute in child.substmts:
                # process the 'type' attribute:
                # Currently integer, enumeration and string are supported.
                if attribute.keyword == 'type':
                    distinguish_attribute_type(attribute, node)
                elif attribute.keyword == 'key':
                    listkey = to_lower_camelcase(attribute.arg).split()
                elif attribute.keyword == 'description':
                    node['description'] = attribute.arg
                elif attribute.keyword == 'default':
                    node['default'] = attribute.arg
                elif attribute.keyword == 'mandatory':
                    required_elem_list.append(child.arg)
                    node['x-is-required'] = True if attribute.arg == 'true' else False
                    parent_model = to_upper_camelcase(child.parent.arg)
                    if parent_model not in PARENT_MODELS.keys():
                        PARENT_MODELS[parent_model] = {'models': [], 'discriminator': to_lower_camelcase(child.arg)}
                elif isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "cli-example":
                    node['example'] = attribute.arg
                elif isinstance(attribute.keyword, tuple) and attribute.keyword[1] == "iovnet-class":
                    node['x-inherits-from'] = attribute.arg
                elif attribute.keyword == 'config' and attribute.arg == 'false':
                    config = False
                    node['readOnly'] = True

                # Process the reference to another model.
                # We differentiate between single and array references.
                elif attribute.keyword == 'uses':
                    # Workaround to make it working
                    continue

                    if len(attribute.arg.split(':')) > 1:
                        attribute.arg = attribute.arg.split(':')[-1]

                    ref_arg = to_upper_camelcase(attribute.arg)
                    # A list is built containing the child elements which are not referenced statements.
                    nonRefChildren = [e for e in child.i_children if not hasattr(e, 'i_uses')]
                    # If a node contains mixed referenced and non-referenced children,
                    # it is a extension of another object, which in swagger is defined using the
                    # "AllOf" statement.
                    ref = '#/definitions/' + ref_arg
                    if not nonRefChildren:
                        referenced = True
                    else:
                        if ref_arg in PARENT_MODELS:
                            PARENT_MODELS[ref_arg]['models'].append(child.arg)
                        node['allOf'] = []
                        node['allOf'].append({'$ref': ref})

        if child.keyword == 'action':
            handle_action_object(child, definitions)
            # Skip processing of action, otherwise they will be
            # considered as properties
            # tree_structure[to_lower_camelcase(child.arg)] = node
            continue

        # When a node contains a referenced model as an attribute the algorithm
        # does not go deeper into the sub-tree of the referenced model.
        if not referenced:
            if not nonRefChildren:
                gen_model_node(child, node, config, definitions=definitions)
            else:
                node_ext = dict()
                properties = dict()
                gen_model(nonRefChildren, properties)
                node_ext['properties'] = properties
                node['allOf'].append(node_ext)

        # Leaf-lists need to create arrays.
        # Copy the 'node' content to 'items' and change the reference
        if child.keyword == 'leaf-list':
            ll_node = {'type': 'array', 'items': node}
            node = ll_node

        # Groupings are class names and upper camelcase.
        # All the others are variables and lower camelcase.
        if child.keyword == 'grouping':
            if referenced:
                node['$ref'] = ref
            node['x-is-yang-grouping'] = True
            tree_structure[to_upper_camelcase(child.arg)] = node

        elif child.keyword == 'list':
            node['type'] = 'array'
            node['items'] = dict()
            if listkey:
                node['x-key'] = listkey
            if referenced:
                node['items'] = {'$ref': ref}
            else:
                if 'allOf' in node:
                    allOf = list(node['allOf'])
                    node['items']['allOf'] = allOf
                    del node['allOf']
                # elif 'properties' in node:
                #    properties = dict(node['properties'])
                #    node['items']['properties'] = properties
                #    del node['properties']
            parent_list = get_parent_list(child)
            parents_name = '_'.join(parent_list) 
            node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)
            if node_schema_name not in definitions:
                definitions[node_schema_name] = dict()
            if 'properties' not in definitions[node_schema_name]:
                # TODO: maybe we have to add an key_index for multikey support
                if node['type'] == 'array':
                    definitions[node_schema_name]['x-is-list'] = 'true'
                node['x-key-list'] = list()
                for key in listkey:
                    node['properties'][key]['x-is-key'] = True
                    key_dict = OrderedDict()
                    key_dict['name'] = key
                    key_dict['type'] = node['properties'][key]['type']
                    if 'enum' in node['properties'][key]:
                        key_dict['isEnum'] = 'true'
                    if 'x-typedef' in node['properties'][key]:
                        key_dict['x-typedef'] = node['properties'][key]['x-typedef']
                    if key_dict['type'] == 'integer':
                        key_dict['format'] = node['properties'][key]['format']
                    node['x-key-list'].append(key_dict)
                definitions[node_schema_name]['properties'] = copy.deepcopy(node['properties'])
                if required_elem_list:
                    definitions[node_schema_name]['required'] = copy.deepcopy(required_elem_list)

            del node['properties']
            node['items']['$ref'] = '#/definitions/{0}'.format(node_schema_name)

            if 'x-inherits-from' in node:
                definitions[node_schema_name]['x-inherits-from'] = node['x-inherits-from']
                del node['x-inherits-from']

            definitions[node_schema_name]['x-parent'] = to_upper_camelcase(((child.parent.arg) if not parents_name else parents_name))
            tree_structure[to_lower_camelcase(child.arg)] = node
        elif child.keyword == 'container':
            parent_list = get_parent_list(child)
            parents_name = '_'.join(parent_list)
            node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)
            if node_schema_name not in definitions:
                definitions[node_schema_name] = dict()

            if 'properties' not in definitions[node_schema_name]:
                definitions[node_schema_name]['properties'] = copy.deepcopy(node['properties'])

            if required_elem_list:
                definitions[node_schema_name]['required'] = copy.deepcopy(required_elem_list)

            node.clear()
            node['$ref'] = '#/definitions/{0}'.format(node_schema_name)
            definitions[node_schema_name]['x-parent'] = to_upper_camelcase(((child.parent.arg) if not parents_name else parents_name))
            tree_structure[to_lower_camelcase(child.arg)] = node

            if 'x-inherits-from' in node:
                definitions[node_schema_name]['x-inherits-from'] = node['x-inherits-from']
                del node['x-inherits-from']
        elif child.keyword == 'input' or child.keyword == 'output':
            parent_list = get_parent_list(child)
            parent_action_list = get_parent_list(child.parent)
            parent_action_name = '_'.join(parent_action_list)
            parents_name = '_'.join(parent_list)
            node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)
            if node_schema_name not in definitions:
                definitions[node_schema_name] = copy.deepcopy(node)
                if required_elem_list:
                    definitions[node_schema_name]['required'] = copy.deepcopy(required_elem_list)

            node.clear()
            node['$ref'] = '#/definitions/{0}'.format(node_schema_name)
            definitions[node_schema_name]['x-parent'] = to_upper_camelcase(
                child.parent.arg if not parents_name else parent_action_name)
            definitions[node_schema_name]['x-is-yang-action-object'] = True
            tree_structure[to_lower_camelcase(child.arg)] = node

            if 'x-inherits-from' in node:
                definitions[node_schema_name]['x-inherits-from'] = node['x-inherits-from']
                del node['x-inherits-from']

        # elif child.keyword == 'leaf':
        #    copy_node = dict()
        #    copy_node['properties'] = dict()
        #    copy_node['properties'][to_lower_camelcase(child.arg)] = dict.copy(node)

        #    tree_structure[to_lower_camelcase(child.arg)] = copy_node
        else:
            if referenced:
                node['$ref'] = ref

            if child.keyword == 'input' or child.keyword == 'output':
                # TODO: This is because pyang does not support the action keyword
                child.arg = str(child.keyword)

            if node:
                tree_structure[to_lower_camelcase(child.arg)] = node


def handle_action_object(child, definitions):
    if not definitions:
        return

    parent_list = get_parent_list(child)
    parents_name = '_'.join(parent_list)
    parents_name_upper = to_upper_camelcase(parents_name)
    node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)

    action_dict = dict()
    action_dict['x-yang-action-baseName'] = child.arg
    action_dict['x-yang-action-name-upper-camelcase'] = to_upper_camelcase(child.arg)
    action_dict['x-yang-action-name-lower-camelcase'] = to_lower_camelcase_real(child.arg)
    action_dict['x-yang-action-has-input'] = False
    action_dict['x-yang-action-has-output'] = False

    for action_child in child.i_children:
        if action_child.keyword == 'input' and action_child.i_children:
            action_dict['x-yang-action-has-input'] = True
            action_dict['x-yang-action-input-object'] = to_upper_camelcase(node_schema_name + "_input")

        if action_child.keyword == 'output' and action_child.i_children:
            action_dict['x-yang-action-has-output'] = True
            action_dict['x-yang-action-output-object'] = to_upper_camelcase(node_schema_name + "_output")

    if parents_name_upper not in definitions:
        definitions[parents_name_upper] = dict()

    definitions[parents_name_upper]['x-has-yang-actions'] = True
    if 'x-yang-actions' not in definitions[parents_name_upper]:
        definitions[parents_name_upper]['x-yang-actions'] = list()

    already_in_list = False
    for elem in definitions[parents_name_upper]['x-yang-actions']:
        if elem['x-yang-action-baseName'] == action_dict['x-yang-action-baseName']:
            already_in_list = True
            break

    if not already_in_list:
        definitions[parents_name_upper]['x-yang-actions'].append(action_dict)


def get_parent_list(child):
    parent = child.parent
    parent_list = list()
    while parent is not None:
        parent_list.append(parent.arg)
        parent = parent.parent

    return list(reversed(parent_list[:-1]))


def get_parent_schema_list(child):
    parent = child.parent
    parent_list = list()
    while parent is not None:
        parent_list.append(to_upper_camelcase(parent.arg))
        parent = parent.parent

    parent_list = list(reversed(parent_list))
    final_list = list()
    for i, elem in enumerate(parent_list,start=1):
        subparentlist=parent_list[1:i]
        schema_name = to_upper_camelcase('_'.join(subparentlist))
        if schema_name:
            final_list.append(schema_name)
        else:
            final_list.append(elem)

    return final_list


def gen_model_node(node, tree_structure, config=True, definitions=None):
    """ Generates the properties sub-tree of the current node."""
    if hasattr(node, 'i_children'):
        properties = {}
        children_list = node.i_children if node.i_children else node.substmts
        gen_model(children_list, properties, config, definitions=definitions)
        if properties:
            tree_structure['properties'] = properties


def generate_yang_lib_api():
    get = dict()
    get['description'] = "Read YANG library version revision date"
    get['parameters'] = list()
    get['produces'] = ['application/json']
    get['consumes'] = []
    get['operationId'] = to_upper_camelcase('read' + _ROOT_NODE_NAME + 'LibraryVersion')
    get['tags'] = [_ROOT_NODE_NAME]
    get['responses'] = {
        '200': {'description': 'OK: Successful operation'},
        '400': {'description': 'Bad request'},
        '404': {'description': 'Not found'},
        '405': {'description': 'Method not allowed: Use POST to invoke operations'}
    }
    return get


def gen_apis(children, path, apis, definitions, config=True, is_root=False):
    """ Generates the swagger path tree for the APIs."""
    for child in children:
        if is_root:
            global _ROOT_NODE_NAME
            _ROOT_NODE_NAME = child.arg
        if not hasattr(child, 'i_is_key') or not child.i_is_key:
            gen_api_node(child, path, apis, definitions, config)

    # apis['/yang-library-version'] = dict()
    # apis['/yang-library-version']['get'] = generate_yang_lib_api() #"2016-06-21"
    # found in the repository: /modules/ietf/ietf-yang-library.yang


def gen_api_for_node_list(node, schema, config, keyList, path, definitions):
    # Key statement must be present if config statement is True and may
    # be present otherwise.
    if config:
        for key in keyList:
            if not key:
                raise Exception('Invalid list statement, key parameter is required')

    # It is checked that there is not name duplication within the input parameters list (i.e., path).
    # In case of duplicity the input param. is upgrade to node.arg
    # (parent node name) + _ + the input param (key).
    # Example:
    #          /config/Context/{uuid}/_topology/{uuid}/_link/{uuid}/_transferCost/costCharacteristic/{costAlgorithm}/
    #
    # is replaced by:
    #
    #          /config/Context/{uuid}/_topology/{topology_uuid}/_link/{link_uuid}/_transferCost/costCharacteristic/{costAlgorithm}/
    for key in keyList:
        if key:
            match = re.search(r"\{([A-Za-z0-9_]+)\}", path)
            if match and key == match.group(1):
                if node.arg[0] == '_':
                    new_param_name = node.arg[1:] + '_' + to_lower_camelcase(key)
                else:
                    new_param_name = node.arg + '_' + to_lower_camelcase(key)
                path += '{' + new_param_name + '}/'
                for child in node.i_children:
                    if child.arg == key:
                        child.arg = new_param_name
            else:
                path += '{' + to_lower_camelcase(key) + '}/'

    schema_list = {}
    gen_model([node], schema_list, config, definitions=definitions)

    # If a body input params has not been defined as a schema (not included in the definitions set),
    # a new definition is created, named the parent node name and the extension Schema
    # (i.e., NodenameSchema). This new definition is a schema containing the content
    # of the body input schema i.e {"child.arg":schema} -> schema
    if '$ref' not in schema_list[to_lower_camelcase(node.arg)]['items']:
        definitions[to_upper_camelcase(node.arg)] = dict(
            schema_list[to_lower_camelcase(node.arg)]['items'])
        schema['$ref'] = '#/definitions/{0}'.format(to_upper_camelcase(node.arg))
    else:
        schema = dict(schema_list[to_lower_camelcase(node.arg)]['items'])

    return path, schema


def gen_api_for_node_rpc(node, schema, config, path, definitions, apis):
    schema_out = dict()
    list_to_iterate = node.i_children if hasattr(node, 'i_children') and node.i_children else node.substmts

    for child in list_to_iterate:
        if child.keyword == 'input' and child.i_children:
            # TODO: This is done because pyang does not support the action keyword
            child.arg = 'input'
            gen_model([child], schema, config, definitions=definitions)

            # If a body input params has not been defined as a schema (not included in the definitions set),
            # a new definition is created, named the parent node name and the extension Schema
            # (i.e., NodenameRPCInputSchema). This new definition is a schema containing the content
            # of the body input schema i.e {"child.arg":schema} -> schema
            parent_list = get_parent_list(child)
            parents_name = '_'.join(parent_list)
            node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)

            if schema[to_lower_camelcase(child.arg)]:
                if '$ref' not in schema[to_lower_camelcase(child.arg)]:
                    definitions[to_upper_camelcase(node_schema_name + ('_rpc' if node.keyword == 'rpc'
                                                   else ''))] = schema[
                        to_lower_camelcase(child.arg)]
                    schema = {'$ref': '#/definitions/' + to_upper_camelcase(node_schema_name + ('_rpc'
                                                                            if node.keyword == 'rpc'
                                                                            else ''))}
                else:
                    schema = schema[to_lower_camelcase(child.arg)]
            else:
                schema = None

        elif child.keyword == 'output' and child.i_children:
            # TODO: This is done because pyang does not support the action keyword
            child.arg = 'output'
            gen_model([child], schema_out, config, definitions=definitions)

            # If a body input params has not been defined as a schema (not included in the definitions set),
            # a new definition is created, named the parent node name and the extension Schema
            # (i.e., NodenameRPCOutputSchema). This new definition is a schema containing the content
            # of the body input schema i.e {"child.arg":schema} -> schema
            parent_list = get_parent_list(child)
            parents_name = '_'.join(parent_list)
            node_schema_name = to_upper_camelcase(parents_name + ('_' if parent_list else '') + child.arg)

            if schema_out[to_lower_camelcase(child.arg)]:
                if '$ref' not in schema_out[to_lower_camelcase(child.arg)]:
                    definitions[to_upper_camelcase(node_schema_name + ('_rpc' if node.keyword == 'rpc' else ''))] = \
                        schema_out[to_lower_camelcase(child.arg)]
                    schema_out = {'$ref': '#/definitions/' + to_upper_camelcase(node_schema_name + ('_rpc'
                                                                                if node.keyword == 'rpc'
                                                                                else ''))}
                else:
                    schema_out = schema_out[to_lower_camelcase(child.arg)]
            else:
                schema_out = None

    apis[str(path)] = print_rpc(node, schema, path, definitions, schema_out)


# Generates the API of the current node.
def gen_api_node(node, path, apis, definitions, config=True):
    """ Generate the API for a node."""
    path += str(node.arg) + '/'
    list_path = str(path)
    tree = {}
    schema = {}
    keyList = []
    for sub in node.substmts:
        # If config is False the API entry is read-only.
        if sub.keyword == 'config' and sub.arg == 'false':
            config = False
        elif sub.keyword == 'key':
            keyList = str(sub.arg).split()
        elif sub.keyword == 'uses':
            # Set the reference to a model, previously defined by a grouping.
            schema['$ref'] = '#/definitions/{0}'.format(to_upper_camelcase(sub.arg))

    # API entries are only generated from container and list nodes.
    if node.keyword == 'list' or node.keyword == 'container' or node.keyword == 'leaf':
        if not node.keyword == 'leaf':
            nonRefChildren = [e for e in node.i_children if not hasattr(e, 'i_uses')]
        # We take only the schema model of a single item inside the list as a "body"
        # parameter or response model for the API implementation of the list statement.
        if node.keyword == 'list':
            path, schema = gen_api_for_node_list(node, schema, config, keyList, path, definitions)

        elif node.keyword == 'container':
            gen_model([node], schema, config, definitions=definitions)

            # If a body input params has not been defined as a schema (not included in the definitions set),
            # a new definition is created, named the parent node name and the extension Schema
            # (i.e., NodenameSchema). This new definition is a schema containing the content
            # of the body input schema i.e {"child.arg":schema} -> schema
            if '$ref' not in schema[to_lower_camelcase(node.arg)]:
                definitions[to_upper_camelcase(node.arg)] = schema[to_lower_camelcase(node.arg)]
                schema['$ref'] = '#/definitions/' + to_upper_camelcase(node.arg)
            else:
                schema = schema[to_lower_camelcase(node.arg)]

        elif node.keyword == 'leaf':
            gen_model([node], schema, config, definitions=definitions)

            # There is only one attribute, I do not want to create a new schema for this
            updated_schema = dict()
            updated_schema = dict.copy(schema[to_lower_camelcase(node.arg)])
            schema = updated_schema

        if 'is_restconf_path' in locals() and is_restconf_path:
            path = '/data' + str(path)

        if node.keyword == 'leaf':
            new_schema = schema
        else:
            new_schema = {"$ref": schema['$ref']}

        apis[str(path)] = print_api(node, config, new_schema, path, definitions)

        if node.keyword == 'list':
            list_schema = {
                "type": "array",
                "items": {"$ref": schema['$ref']}
            }
            apis[str(list_path)] = print_api(node, config, list_schema, list_path, definitions, is_list=True)

    elif node.keyword == 'rpc' or node.keyword == 'action':
        gen_api_for_node_rpc(node, schema, config, path, definitions, apis)
        return apis

    elif node.keyword == 'notification':
        schema_out = dict()
        gen_model([node], schema_out)
        # For the API generation we pass only the content of the schema i.e {"child.arg":schema} -> schema
        schema_out = schema_out[to_lower_camelcase(node.arg)]
        apis['/streams' + str(path)] = print_notification(node, schema_out)
        return apis

    # Generate APIs for children.
    if hasattr(node, 'i_children'):
        # The param is_root is used to add the tag for each API. Every root container in the YANG model
        # represents a different tag in the APIs
        gen_apis(node.i_children, path, apis, definitions, config, is_root=False)


def gen_typedefs(typedefs):
    for typedef in typedefs:
        type = {'name': typedef.arg}
        for attribute in typedef.substmts:
            if attribute.keyword == 'type':
                if attribute.arg[:-2] == 'int' or attribute.arg[:-2] == 'uint' or attribute.arg[:-1] == 'int' or attribute.arg[:-1] == 'uint':
                    type['type'] = 'integer'
                    type['format'] = attribute.arg
                elif attribute.arg == 'enumeration':
                    type['type'] = 'enumeration'
                    type['enum'] = [e[0]
                                    for e in attribute.i_type_spec.enums]
                # map all other types to string
                else:
                    type['type'] = 'string'
        TYPEDEFS[typedef.arg] = type


def print_notification(node, schema_out):
    operations = {'get': generate_retrieve(node, schema_out, None)}
    operations['get']['schemes'] = ['ws']
    return operations


def print_rpc(node, schema_in, path, definitions, schema_out):
    operations = {}
    if node.keyword == 'leaf':
        node_name = node.parent
    else:
        node_name = node
    parent_list = get_parent_schema_list(node_name)
    parents_name = parent_list[-1] if len(parent_list) > 1 else ''
    parent_set = set(parent_list)
    node_schema_name = to_upper_camelcase(node_name.arg) if not parents_name else to_upper_camelcase(
        parents_name + '_' + node_name.arg)

    if node.keyword == 'action':
        for child in node.i_children:
            if child.keyword == 'input' and child.i_children:
                parent_set.add(to_upper_camelcase(node_schema_name + '_input'))
            elif child.keyword == 'output' and child.i_children:
                parent_set.add(to_upper_camelcase(node_schema_name + '_output'))
    else:
        parent_set.add(node_schema_name)

    schema_list = list(parent_set)

    operations['post'] = generate_create(node, schema_in, path, definitions, schema_list, rpc=schema_out)
    return operations


# print the API JSON structure.
def print_api(node, config, ref, path, definitions, is_list=False):
    """ Creates the available operations for the node."""
    operations = {}
    if node.keyword == 'leaf':
        node_name = node.parent
    else:
        node_name = node
    parent_list = get_parent_schema_list(node_name)
    parents_name = parent_list[-1] if len(parent_list) > 1 else ''
    node_schema_name = to_upper_camelcase(node_name.arg) if not parents_name else to_upper_camelcase(parents_name + '_' + node_name.arg)
    parent_set = set(parent_list)
    parent_set.add(node_schema_name)
    schema_list = list(parent_set)

    if config and config != 'false':
        operations['post'] = generate_create(node, ref, path, definitions, schema_list, is_list=is_list)
        operations['get'] = generate_retrieve(node, ref, path, definitions, schema_list, is_list=is_list)
        operations['patch'] = generate_update(node, ref, path, definitions, schema_list, is_list=is_list)
        operations['put'] = generate_replace(node, ref, path, definitions, schema_list, is_list=is_list)
        operations['delete'] = generate_delete(node, ref, path, definitions, schema_list, is_list=is_list)
        if 'generate_all_restconf_methods' in locals() and generate_all_restconf_methods:
            operations['options'] = generate_discovery(node, ref, path, definitions, schema_list, is_list=is_list)
            operations['head'] = generate_header_retrieval(node, ref, path, definitions, schema_list, is_list=is_list)
    else:
        operations['get'] = generate_retrieve(node, ref, path, definitions, schema_list, is_list=is_list)
    if S_API or node.keyword == 'leaf':
        # or node.arg == _ROOT_NODE_NAME:
        if 'post' in operations: del operations['post']
        if 'delete' in operations: del operations['delete']
        if 'put' in operations: del operations['put']

    return operations


def get_input_path_parameters(path):
    """"Get the input parameters from the path url."""
    path_params = []
    params = path.split('/')
    for param in params:
        if len(param) > 0 and param[0] == '{' and param[len(param) - 1] \
                == '}':
            path_params.append(param[1:-1])
    return path_params

###########################################################
############### Creating CRUD Operations ##################
###########################################################


# CREATE
def generate_create(stmt, schema, path, definitions, schema_list, rpc=None, is_list=False):
    """ Generates the create function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    post = {}
    generate_api_header(stmt, post, 'Create', path, is_list=is_list)
    # Input parameters
    if path:
        post['parameters'] = create_parameter_list(path_params, schema, definitions, schema_list)
    else:
        post['parameters'] = []
    in_params = create_body_dict(stmt.arg, schema)
    if in_params:
        post['parameters'].append(in_params)
    else:
        if not post['parameters']:
            del post['parameters']
    # Responses
    if rpc:
        response = {
            '200': {'description': 'OK: Successful operation'},
            '204': {'description': 'No content: Successful operation'},
            '403': {'description': 'Forbidden: User not authorized'},
            '404': {'description': 'Operation not found'}
        }
        response['200']['schema'] = rpc
    else:
        response = {
            '201': {'description': 'Created: Successful operation'},
            '403': {'description': 'Forbidden: User not authorized'},
            '404': {'description': 'Not found: Resource not created'},
            '409': {'description': 'Conflict: Resource not created'}
        }
    post['responses'] = response
    return post


# RETRIEVE

def generate_retrieve(stmt, schema, path, definitions, schema_list, is_list=False):
    """ Generates the retrieve function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    get = {}
    generate_api_header(stmt, get, 'Read', path, stmt.keyword == 'container'
                        and not path_params, is_list=is_list)
    if path:
        get['parameters'] = create_parameter_list(path_params, schema, definitions, schema_list)

    # Responses
    response = {
        '200': {'description': 'OK: Successful operation'},
        '400': {'description': 'Bad request'},
        '404': {'description': 'Not found'},
        '405': {'description': 'Method not allowed: Use POST to invoke operations'}
    }
    if schema:
       response['200']['schema'] = schema
       if 'enum' in schema:
           response['200']['x-is-enum'] = 'true'
       if 'x-typedef' in schema:
            response['200']['x-typedef'] = schema['x-typedef']
    get['responses'] = response
    return get


# UPDATE
def generate_update(stmt, schema, path, definitions, schema_list, is_list=False):
    """ Generates the update function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    patch = {}
    generate_api_header(stmt, patch, 'Update', path, is_list=is_list)
    # Input parameters
    if path:
        patch['parameters'] = create_parameter_list(path_params, schema, definitions, schema_list)
    else:
        patch['parameters'] = []
    in_params = create_body_dict(stmt.arg, schema)
    if in_params:
        patch['parameters'].append(in_params)
    else:
        if not patch['parameters']:
            del patch['parameters']
    # Responses
    response = {
        '200': {'description': 'OK: Successful update'},
        '204': {'description': 'No content: Successful update'},
        '403': {'description': 'Forbidden: User not authorized'},
        '404': {'description': 'Resource not found'}
    }

    patch['responses'] = response
    return patch


# PUT
def generate_replace(stmt, schema, path, definitions, schema_list, is_list=False):
    """ Generate the put function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    put = {}
    generate_api_header(stmt, put, 'Replace', path, is_list=is_list)
    if path:
        put['parameters'] = create_parameter_list(path_params, schema, definitions, schema_list)
    else:
        put['parameters'] = []
    
    in_params = create_body_dict(stmt.arg, schema)

    if in_params:
        put['parameters'].append(in_params)
    else:
        if not put['parameters']:
            del put['parameters']

    response = {
        '201': {'description': 'OK: Resource replaced successfully'},
        '204': {'description': 'No content: Resource modified successfully'},
        '400': {'description': 'Bad request: resource not replaced'},
        '404': {'description': 'Resource not found'}
    }
    put['responses'] = response
    return put


# DELETE
def generate_delete(stmt, ref, path, definitions, schema_list, is_list=False):
    """ Generates the delete function definitions."""
    path_params = get_input_path_parameters(path)
    delete = {}
    generate_api_header(stmt, delete, 'Delete', path, is_list=is_list)
    # Input parameters
    if path_params:
        delete['parameters'] = create_parameter_list(path_params, ref, definitions, schema_list)

    # Responses
    response = {
        '204': {'description': 'No content: Resource deleted'},
        '403': {'description': 'Forbidden: User not authorized'},
        '404': {'description': 'Resource not found'}
    }
    delete['responses'] = response
    return delete


# OPTIONS
def generate_discovery(stmt, ref, path, definitions, schema_list, is_list=False):
    """ Generate the options function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    options = {}
    generate_api_header(stmt, options, 'Discovery', path, is_list=is_list)
    if path:
        options['parameters'] = create_parameter_list(path_params, ref, definitions, schema_list)

    response = {
        '200': {'description': 'OK: Successful operation'}
    }
    options['responses'] = response
    return options


# HEAD
def generate_header_retrieval(stmt, ref, path, definitions, schema_list, is_list=False):
    """ Generate the head function definitions."""
    path_params = None
    if path:
        path_params = get_input_path_parameters(path)
    head = {}
    generate_api_header(stmt, head, 'Header Get', path, is_list=is_list)
    if path:
        head['parameters'] = create_parameter_list(path_params, ref, definitions, schema_list)

    response = {
        '200': {'description': 'OK: Successful operation'}
    }
    head['responses'] = response
    return head


def create_parameter_list(path_params, schema, definitions, schema_list):
    """ Create description from a list of path parameters."""
    param_list = []
    for i, param in enumerate(path_params):
        parameter = dict()
        parameter['in'] = 'path'
        parameter['name'] = str(param)
        parameter['description'] = 'ID of ' + str(param)
        parameter['required'] = True

        if not fill_right_type_for_path_param(schema, param, definitions, parameter, schema_list):
            parameter['type'] = 'string'

        param_list.append(parameter)
    return param_list


def fill_right_type_for_path_param(schema, param, definitions, parameter, schema_list):
    found = False

    for j, _ in enumerate(schema_list):
        schema = definitions[str(schema_list[j])]
        if str(param) in schema['properties']:
            parameter['type'] = schema['properties'][str(param)]['type'] if 'type' in schema['properties'][str(param)] else 'string'
            parameter['format'] = schema['properties'][str(param)]['format'] if 'format' in schema['properties'][str(param)] else ''
            parameter['enum'] = schema['properties'][str(param)]['enum'] if 'enum' in schema['properties'][str(param)] else ''
            parameter['x-typedef'] = schema['properties'][str(param)]['x-typedef'] if 'x-typedef' in schema['properties'][str(param)] else ''
            found = True
            break;
    if not found:
        if '_' in str(param):
            param_name = str(param).split('_');
            for j, _ in enumerate(schema_list):
                if param_name[0].title() == str(schema_list[j]):
                    schema = definitions[str(schema_list[j])]
                    if param_name[-1] in schema['properties']:
                        parameter['type'] = schema['properties'][param_name[-1]]['type'] if 'type' in schema['properties'][param_name[-1]] else 'string'
                        parameter['format'] = schema['properties'][param_name[-1]]['format'] if 'format' in schema['properties'][param_name[-1]] else ''
                        parameter['enum'] = schema['properties'][param_name[-1]]['enum'] if 'enum' in schema['properties'][param_name[-1]] else ''
                        parameter['x-typedef'] = schema['properties'][param_name[-1]]['x-typedef'] if 'x-typedef' in schema['properties'][param_name[-1]] else ''
                        found = True
                        break;
        
    if 'format' in parameter and not parameter['format']:
        del parameter['format']
    
    if 'enum' in parameter and not parameter['enum']:
        del parameter['enum']
    if 'x-typedef' in parameter and not parameter['x-typedef']:
        del parameter['x-typedef']
        
    return found


def create_body_dict(name, schema):
    """ Create a body description from the name and the schema."""
    body_dict = {}
    if schema:
        body_dict['in'] = 'body'
        body_dict['name'] = name
        body_dict['schema'] = schema
        if 'description' in schema:
            body_dict['description'] = schema['description']
        else:
            body_dict['description'] = name + 'body object'
        if 'enum' in schema:
            body_dict['x-is-enum'] = 'true'
        if 'x-typedef' in schema:
            body_dict['x-typedef'] = schema['x-typedef']
        body_dict['required'] = True
    return body_dict


def create_responses(name, schema=None):
    """ Create generic responses based on the name and an optional schema."""
    response = {
        '200': {'description': 'Successful operation'},
        '400': {'description': 'Internal Error'}
    }
    if schema:
        response['200']['schema'] = schema
        if 'enum' in schema:
            response['200']['x-is-enum'] = 'true'
        if 'x-typedef' in schema:
            response['200']['x-typedef'] = schema['x-typedef']
    return response


def generate_api_header(stmt, struct, operation, path, is_collection=False, is_list=False):
    """ Auxiliary function to generate the API-header skeleton.
    The "is_collection" flag is used to decide if an ID is needed.
    """
    child_path = False
    # parent_container = [to_upper_camelcase(element) for i, element in enumerate(str(path).split('/')[1:-1]) if
    #                   str(element)[0] == '{' and str(element)[-1] == '}']

    path_without_keys = [element for element in str(path).strip('/').split('/')
                         if not str(element)[0] == '{' and not str(element)[-1] == '}']

    parent_container = str(path_without_keys[0]) if path_without_keys else 'default'

    if len(path_without_keys) > 1:
        child_path = True
        parent_container = ''.join([to_upper_camelcase(element) for element in path_without_keys[:-1]])

    struct['summary'] = '%s %s%s' % (
        str(operation), str(stmt.arg),
        ('' if is_collection else ' by ID'))
    struct['description'] = str(operation) + ' operation of resource: ' + str(stmt.arg)
    struct['operationId'] = '%s%s%s%s%s' %  (str(operation).lower(),
                                            (parent_container if child_path else ''),
                                            to_upper_camelcase(stmt.arg),
                                            ('List' if is_list else ''),
                                            ('' if is_collection else 'ByID'))
    struct['produces'] = ['application/json']
    struct['consumes'] = ['application/json']

    if _ROOT_NODE_NAME:
        struct['tags'] = [_ROOT_NODE_NAME]


def to_lower_camelcase(name):
    """ Converts the name string to lower camelcase by using "-" and "_" as
    markers.
    """
    return name
    # return re.sub(r"(?:\B_|\b\-)([a-zA-Z0-9])", lambda l: l.group(1).upper(), name)

def to_lower_camelcase_real(name):
    """ Converts the name string to lower camelcase by using "-" and "_" as
    markers.
    """
    return re.sub(r"(?:\B_|\b\-)([a-zA-Z0-9])", lambda l: l.group(1).upper(), name)


def to_upper_camelcase(name):
    """ Converts the name string to upper camelcase by using "-" and "_" as
    markers.
    """
    return re.sub(r"(?:\B_|\b\-|^)([a-zA-Z0-9])", lambda l: l.group(1).upper(), name)
