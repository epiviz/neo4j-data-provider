import utils
import ujson
import pandas

def get_data(in_params_selection, in_params_order, in_params_selected_levels, in_params_nodeId, in_params_depth):

    root_node = in_params_nodeId

    if in_params_nodeId == "":
        root_node = "0-0"

    qryStr = "MATCH (f:Feature {id:'" + root_node + "'})-[:PARENT_OF*0..3]->(f2:Feature) " \
                "with collect(f2) + f as nodesFeat unwind nodesFeat as ff " \
                "return distinct ff.lineage as lineage, ff.start as start, ff.label as label, " \
                "ff.leafIndex as leafIndex, ff.parentId as parentId, ff.depth as depth, ff.partition as partition, " \
                "ff.end as end, ff.id as id, ff.lineageLabel as lineageLabel, ff.nchildren as nchildren, ff.nleaves as nleaves, " \
                "ff.order as order " \
                "order by ff.leafIndex, ff.order"


    rq_res = utils.cypher_call(qryStr)
    df = utils.process_result(rq_res)

    # convert columns to int
    df['index'] = df['index'].astype(int)
    df['start'] = df['start'].astype(int)
    df['end'] = df['end'].astype(int)
    df['order'] = df['order'].astype(int)
    df['leafIndex'] = df['leafIndex'].astype(int)
    df['nchildren'] = df['nchildren'].astype(int)
    df['nleaves'] = df['nleaves'].astype(int)
    df['depth'] = df['depth'].astype(int)

    # restore current order, selection and levels from input params
    for key in in_params_order.keys():
        df.loc[df['id'] == key, 'order'] = in_params_order[key]

    for key in in_params_selection.keys():
        df.loc[df['id'] == key, 'selectionType'] = in_params_selection[key]

    for key in in_params_selected_levels.keys():
        df.loc[df['depth'] == key, 'selectionType'] = in_params_selection[key]

    root = df[df['id'].str.contains(root_node)].iloc[0]
    other = df[~df['id'].str.contains(root_node)]

    rootDict = row_to_dict(root)
    result = df_to_tree(rootDict, other)

    print(ujson.dumps(result))

def row_to_dict(row):
    toRet = {}
    toRet['lineage'] = row['lineage']
    toRet['end'] = row['end']
    toRet['partition'] = row['partition']
    toRet['leafIndex'] = row['leafIndex']
    toRet['nchildren'] = row['nchildren']
    toRet['label'] = row['label']
    toRet['name'] = row['label']
    toRet['start'] = row['start']
    toRet['depth'] = row['depth']
    toRet['globalDepth'] = row['depth']
    toRet['lineageLabel'] = row['lineageLabel']
    toRet['nleaves'] = row['nleaves']
    toRet['parentId'] = row['parentId']
    toRet['order'] = row['order']
    toRet['id'] = row['id']
    toRet['selectionType'] = 1
    toRet['size'] = 1
    toRet['children'] = []
    return toRet

def df_to_tree(root, df):

    if len(df) == 0:
        root['children'] = None
        return

    children = df[df['parentId'].str.contains(root['id'])]
    otherChildren = df[~df['parentId'].str.contains(root['id'])]
    children.sort_values('order')
    root['size'] = len(children)

    for index,row in children.iterrows():
        childDict = row_to_dict(row)
        subDict = df_to_tree(childDict, otherChildren)
        root['children'].append(subDict)

    return root