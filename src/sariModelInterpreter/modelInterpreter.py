import re
import sys
import yaml

def compilePath(child, parentPath=''):
    """
    Generates the query paths for a given child and all its children

    >>> child = {"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "query" : "$subject crm:P14_carried_out_by ?value ." }] }] }
    >>> print(compilePath(child, ""))
    $subject crm:P128_carries ?value_work .
    $subject crm:P128_carries/crm:P94i_was_created_by ?value_work_creation .
    $subject crm:P128_carries/crm:P94i_was_created_by/crm:P14_carried_out_by ?value_work_creator .
    """
    query = child['query']
    optional = child['optional'] if 'optional' in child else False
    
    subjectPathPattern = r'(?:\$subject\s)([^\s]*)'
    subjectPath = re.search(subjectPathPattern, query).group(1)
    
    completePath = parentPath + '/' + subjectPath if parentPath else subjectPath

    query = query.replace(subjectPath, completePath)
    
    # Namespace variables by prefixing them with (unique) field id
    query = namespaceVariablesInQuery(query, child['id'])
    
    if optional:
        query = "OPTIONAL { %s }\n" % query
    
    if 'children' in child:
        for c in child['children']:
            query = query + "\n" + compilePath(c, completePath)
    
    return query

def compileQuery(node, **kwargs):
    """
    Generates a SPARQL query starting from a given node as subject and traversing through all children
    
    Keyword arguments:
    distinct -- use distinct keyword in select (default False)
    limit -- a limit for the query (default None)
    select -- a list of variables to use in the select statement (default None, uses value and label variables from model)

    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value ." }] }] }]}
    >>> print(compileQuery(node))
    SELECT $subject ?value_work ?value_work_creation ?value_work_creator {
    $subject a crm:E22_Human-Made_Object .
    $subject crm:P128_carries ?value_work .
    $subject crm:P128_carries/crm:P94i_was_created_by ?value_work_creation .
    OPTIONAL { $subject crm:P128_carries/crm:P94i_was_created_by/crm:P14_carried_out_by ?value_work_creator . }
    }

    >>> print(compileQuery(node, distinct=True, limit=10, select=['work_creator']))
    SELECT DISTINCT ?value_work_creator {
    $subject a crm:E22_Human-Made_Object .
    $subject crm:P128_carries ?value_work .
    $subject crm:P128_carries/crm:P94i_was_created_by ?value_work_creation .
    OPTIONAL { $subject crm:P128_carries/crm:P94i_was_created_by/crm:P14_carried_out_by ?value_work_creator . }
    } LIMIT 10
    """
    
    query = "SELECT "
    
    if 'distinct' in kwargs:
        if kwargs['distinct'] == True:
            query += "DISTINCT "
    
    if 'select' in kwargs:
        variables = ' '.join(namespaceSelectsForNode(kwargs['select'], node))
    else:
        variables = "$subject " + ' '.join(getNamespacedValuesAndLabels(node))    
    
    query += variables
    query += " {\n"
    
    query += "$subject a " + node['type'] + " .\n"
    for child in node['children']:
        query += compilePath(child)
        
    query += "}"
    if 'limit' in kwargs:
         query += " LIMIT " + str(kwargs['limit'])
    return query

def getNamespacedValuesAndLabels(node):
    """"
    Returns a list of all value and label variables in a model's children queries and adds the node's id as namespace

    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value . ?value rdfs:label ?label" }] }] }]}
    >>> getNamespacedValuesAndLabels(node)
    ['?label_work_creator', '?value_work', '?value_work_creation', '?value_work_creator']
    """

    def getQueries(children):
        for child in children:
            if 'query' in child:
                queries.append(namespaceVariablesInQuery(child['query'], child['id']))
            if 'children' in child:
                getQueries(child['children'])
                
    queries = []
    if 'children' in node:
        getQueries(node['children'])
        
    allQueries = ' '.join(queries)
    matches = re.findall(r'((?:\?value[^\s/,:,\-\\\(\)]*)|(?:\?label[^\s/,:,\-\\\(\)]*))', allQueries)
    valuesAndLabels = list(set(matches))
    valuesAndLabels.sort()
    return valuesAndLabels


def getQueryForId(id, node):
    """
    Traverses a node and its children and returns the query for the node that matches the given id.
    Returns False if the given node does not contain a query

    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value . ?value rdfs:label ?label" }] }] }]}
    >>> getQueryForId("work_creator", node)
    '$subject crm:P14_carried_out_by ?value . ?value rdfs:label ?label'

    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value . ?value rdfs:label ?label" }] }] }]}
    >>> getQueryForId("artwork", node)
    False
    """
    
    def traverseNode(id, node):
        if node['id'] == id and 'query' in node:
            query.append(node['query'])
        elif 'children' in node:
            for child in node['children']:
                traverseNode(id, child)

    query = []
    traverseNode(id, node)
    
    if len(query):
        return query[0]
    else:
        return False

def namespaceSelectsForNode(selects, node):
    """
    Takes list of ids to select as SPARQL variables and returns namespaced variables

    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value . ?value rdfs:label ?label" }] }] }]}
    >>> namespaceSelectsForNode(['work_creation'], node)
    ['?value_work_creation']

    >>> namespaceSelectsForNode(['work_creator'], node)
    ['?value_work_creator', '?label_work_creator']

    >>> namespaceSelectsForNode(['custom_variable', 'work_creator'], node)
    ['?custom_variable', '?value_work_creator', '?label_work_creator']
    """
    namespacedSelects = []
    for select in selects:
        query = getQueryForId(select, node)
        if query:
            namespacedSelects.append("?value_%s" % select)
            if '?label' in query:
                namespacedSelects.append("?label_%s" % select)
        else:
            namespacedSelects.append("?" + select)
            
    return namespacedSelects

def namespaceVariablesInQuery(query, id):
    """
    Adds the id as namespace to all non-bound variables 

    >>> namespaceVariablesInQuery("$subject crm:P128_carries ?value", "work")
    '$subject crm:P128_carries ?value_work'

    >>> namespaceVariablesInQuery("$subject crm:P9_consists_of ?subcreation; crm:P14_carried_out_by ?value .", "work_creation")
    '$subject crm:P9_consists_of ?subcreation_work_creation; crm:P14_carried_out_by ?value_work_creation .'

    """
    return re.sub(r'\?([^\s/,:;,\-\\\(\)]*)', r'?\1_' + id, query)

def parseModelFromFile(inputFile):
    """
    Reads input model from filepath

    >>> model = parseModelFromFile('../../models/bso.yml')
    >>> print(type(model))
    <class 'list'>
    """
    with open(inputFile, 'r') as f:
        modelData = yaml.safe_load(f.read())
    return modelData

def verifyModel(model):
    """
    Checks if a given model is valid. Returns "Ok" if yes. Otherwise lists errors

    >>> model = [{"id": "artwork", "type": "crm:E22_Man-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "query" : "$subject crm:P14_carried_out_by ?value ." }] }] }] }]
    >>> verifyModel(model)
    'Ok'
    
    >>> model = [{"id": "artwork", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?values .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creation", "query" : "$subject crm:P14_carried_out_by ?value ." }] }] }] }]
    >>> print(verifyModel(model))
    No query or type present in node artwork
    No ?value found in query of work
    Duplicate id work_creation

    >>> model = parseModelFromFile('../../models/bso.yml')
    >>> verifyModel(model)
    'Ok'
    """
    
    def verifyModelNode(node):
        id = None
        if not 'id' in node:
            errors.append("No id present in node")

        id = node['id']

        if not id in ids:
            ids.append(id)
        else:
            errors.append("Duplicate id %s" % id)

        if not 'query' in node and not 'type' in node:
            errors.append("No query or type present in node %s" % id)
        elif 'query' in node:
            if not re.search(r'\$subject\s', node['query']):
                errors.append("No $subject found in query of %s" %id)
            if not re.search(r'\?value[\s|\)]', node['query']):
                errors.append("No ?value found in query of %s" %id)

        if 'children' in node:
            for child in node['children']:
                verifyModelNode(child)

    ids = []
    errors = []
    for node in model:
        verifyModelNode(node)
    
    if len(errors):
        return "\n".join(errors)
    else:
        return "Ok"

if __name__ == '__main__':
    import doctest
    doctest.testmod()