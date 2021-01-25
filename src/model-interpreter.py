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
    query = re.sub(r'\?([^\s/,:,\-\\\(\)]*)', r'?\1_' + child['id'], query)
    
    if optional:
        query = "OPTIONAL { %s }\n" % query
    
    if 'children' in child:
        for c in child['children']:
            query = query + "\n" + compilePath(c, completePath)
    
    return query



def compileQuery(node):
    """
    >>> node = {"id": "artwork", "label": "Artwork", "type": "crm:E22_Human-Made_Object", "children": [{"id": "work", "type": "crm:E36_Visual_Item", "query": "$subject crm:P128_carries ?value .", "children": [{"id": "work_creation", "query": "$subject crm:P94i_was_created_by ?value .", "children" : [{"id": "work_creator", "optional": True, "query" : "$subject crm:P14_carried_out_by ?value ." }] }] }]}
    >>> print(compileQuery(node))
    SELECT * WHERE {
    $subject a crm:E22_Human-Made_Object
    $subject crm:P128_carries ?value_work .
    $subject crm:P128_carries/crm:P94i_was_created_by ?value_work_creation .
    OPTIONAL { $subject crm:P128_carries/crm:P94i_was_created_by/crm:P14_carried_out_by ?value_work_creator . }
    }
    """
    query = "SELECT * WHERE {\n"
    query = query + "$subject a " + node['type'] + "\n"
    for child in node['children']:
        query = query + compilePath(child)
        
    query = query+"}"
    return query


def parseModelFromFile(inputFile):
    """
    Reads input model from filepath

    >>> model = parseModelFromFile('../models/bso.yml')
    >>> print(type(model))
    <class 'list'>
    """
    with open(inputFile, 'r') as f:
        modelData = yaml.safe_load(f.read())
    return modelData


if __name__ == '__main__':
    import doctest
    doctest.testmod()