import utils
import pandas
import sys

"""
.. module:: CombinedRequest
   :synopsis: Query Neo4j Sample nodes and compute aggregation function over selected Feature nodes

.. moduleauthor:: Justin Wagner and Jayaram Kancherla

"""

def get_data(in_params_start, in_params_end, in_params_order, in_params_selection, in_params_selectedLevels,
             in_params_samples, in_datasource):
    """
    Aggregates counts to the selected nodes in the feature hierarchy and returns the counts for the samples selected.

    Args:
        in_params_start: Start of range for features to use during aggregation
        in_params_end: End of range for features to use during aggregation
        in_params_order: Order of features
        in_params_selection: Features nodes and the selection type of expanded, aggregated, or removed
        in_params_selectedLevels: Level of the hierarchy to use
        in_params_samples: Samples to compute aggregation with

    Returns:
        resRowsCols: Aggregated counts for the selected Features over the selected Samples
    """
    tick_samples = in_params_samples.replace("\"", "\'")
    result = None
    error = None
    response_status = 200

    # get the min selected Level if aggregated at multiple levels
    qryStr = "MATCH (s:Sample)-[:COUNT]->(f:Feature)<-[:LEAF_OF]-(:Feature)<-[:PARENT_OF*]-(:Feature)<-[:DATASOURCE_OF]-(ds:Datasource {label: '" + in_datasource + "'}) RETURN f.depth as depth  LIMIT 1"

    try:
        rq_res = utils.cypher_call(qryStr)
        df = utils.process_result(rq_res)

        minSelectedLevel = int(df['depth'].values[0])
        if minSelectedLevel is None:
            minSelectedLevel = 6

        for level in in_params_selectedLevels.keys():
            if in_params_selectedLevels[level] == 2 and int(level) < minSelectedLevel:
                minSelectedLevel = int(level)

        # user selection nodes for custom aggregation - decides the cut
        selNodes = "["
        selFlag = 0
        for node in in_params_selection.keys():
            if "_" in node:
                # its an OTU group node
                group_nodes = node.split("_")
                for gNode in group_nodes:
                    if gNode not in in_params_selection.keys():
                        in_params_selection[gNode] = in_params_selection[node]
                        selNodes += "'" + gNode + "',"
                        selFlag = 1
            elif len(node.split("-")) > 2:
                # its an OTU grouped node. 
                # apply selection to every node in this group
                node_split = node.split("-")
                sNode = node_split[1] + "-" + node_split[2]
                childQryStr = "MATCH (ds:Datasource {label: '" + in_datasource + "'})-[:DATASOURCE_OF]->(:Feature)-[:PARENT_OF*]->(fParent:Feature {id: '" + sNode + "'})-[:PARENT_OF]->(f:Feature) RETURN f.id as id"
                child_rq_res = utils.cypher_call(childQryStr)
                child_df = utils.process_result(child_rq_res)
                children_ids = child_df['id'].values
                for child_node in children_ids:
                    if child_node not in in_params_selection.keys():
                        selNodes += "'" + child_node + "',"
                        in_params_selection[child_node] = 2
                        selFlag = 1

            elif in_params_selection[node] == 2:
                selNodes += "'" +  node + "',"
                selFlag = 1
            elif in_params_selection[node] == 1:
                childQryStr = "MATCH (ds:Datasource {label: '" + in_datasource + "'})-[:DATASOURCE_OF]->(:Feature)-[:PARENT_OF*]->(fParent:Feature {id: '" + node + "'})-[:PARENT_OF]->(f:Feature) RETURN f.id as id"
                child_rq_res = utils.cypher_call(childQryStr)
                child_df = utils.process_result(child_rq_res)
                children_ids = child_df['id'].values
                for child_node in children_ids:
                    if child_node not in in_params_selection.keys():
                        selNodes += "'" + child_node + "',"
                        in_params_selection[child_node] = 2
                        selFlag = 1

        if selFlag == 1:
            selNodes = selNodes[:-1]
        selNodes += "]"

    except:
        error_info = sys.exc_info()
        error = str(error_info[0]) + " " + str(error_info[1]) + " " + str(error_info[2])
        response_status = 500
        return result, error, response_status

    markerGeneOrWgs = ""
    markerGeneOrWgsQyrStr = "MATCH (ds:Datasource {label: '" + in_datasource + "'}) RETURN ds.sequencing_type as sequencing_type"

    try:
        rq_res = utils.cypher_call(markerGeneOrWgsQyrStr)
        df = utils.process_result(rq_res)
        markerGeneOrWgs = df['sequencing_type'].values[0]

    except:
        error_info = sys.exc_info()
        error = str(error_info[0]) + " " + str(error_info[1]) + " " + str(error_info[2])
        response_status = 500
        return result, error, response_status


    if markerGeneOrWgs == "wgs":
        qryStr = "MATCH (ds:Datasource {label: '" + in_datasource + "'}) " \
            "MATCH (ds)-[:DATASOURCE_OF]->(:Feature)-[:PARENT_OF*]->(f:Feature)<-[v:COUNT]-(s:Sample)" \
            "USING INDEX s:Sample(id) WHERE (f.depth=" + str(minSelectedLevel) + " OR f.id IN " + selNodes + ") AND " \
            "(f.start >= " + in_params_start + " AND " \
            "f.end <= " + in_params_end + ") AND s.id IN " + tick_samples + " with distinct f, s, v.val as agg " \
            "RETURN distinct agg, s.id, f.label as label, f.leafIndex as index, f.end as end, f.start as start, " \
            "f.id as id, f.lineage as lineage, f.lineageLabel as lineageLabel, f.order as order"
    else:
        qryStr = "MATCH (ds:Datasource {label: '" + in_datasource + "'}) " \
                 "MATCH (ds)-[:DATASOURCE_OF]->(:Feature)-[:PARENT_OF*]->(f:Feature) MATCH (f)-[:LEAF_OF]->()<-[v:COUNT]-(s:Sample)" \
                 "USING INDEX s:Sample(id) WHERE (f.depth=" + str(minSelectedLevel) + " OR f.id IN " + selNodes + ") AND " \
                 "(f.start >= " + in_params_start + " AND " \
                 "f.end <= " + in_params_end + ") AND s.id IN " + tick_samples + " with distinct f, s, SUM(v.val) as agg " \
                 "RETURN distinct agg, s.id, f.label as label, f.leafIndex as index, f.end as end, f.start as start, " \
                 "f.id as id, f.lineage as lineage, f.lineageLabel as lineageLabel, f.order as order"

    try:
        rq_res = utils.cypher_call(qryStr)
        df = utils.process_result(rq_res)

        root_is_present = True
        for key in in_params_selection.keys():
            lKey = key.split('-')
            if int(lKey[0]) <= minSelectedLevel:
                if in_params_selection[key] == 0 and df.shape == df[df['lineage'].str.contains(key)].shape:
                    root_is_present = False

        if len(df) > 0 and root_is_present:
            # change column type
            df['index'] = df['index'].astype(int)
            df['start'] = df['start'].astype(int)
            df['end'] = df['end'].astype(int)
            df['order'] = df['order'].astype(int)

            # update order based on req
            for key in in_params_order.keys():
                df.loc[df['id'] == key, 'order'] = in_params_order[key]

            for key in in_params_selection.keys():
                if in_params_selection[key] == 0:
                   # user selected nodes to ignore!
                   df = df[~(df['lineage'].str.contains(key))]
                elif in_params_selection[key] == 2:
                   df = df[~(df['lineage'].str.contains(key) & ~df['id'].str.contains(key))]

            for key in in_params_selection.keys():
                if in_params_selection[key] == 2:
                   if df[df['id'].str.contains(key)].shape[0] > 0:
                    node_lineage = df[df['id'].str.contains(key)]['lineage'].head(1).values[0].split(",")
                    for i in range(minSelectedLevel, len(node_lineage)-1):
                       df = df[~df['id'].str.contains(str(node_lineage[i]))]

            # create a pivot_table where columns are samples and rows are features
            # for pandas > 0.17
            df_pivot = pandas.pivot_table(df,
                                    index=["id", "label", "index", "lineage", "lineageLabel", "start", "end", "order"],
                                    columns="s.id", values="agg", fill_value=0).sortlevel("index")

            cols = {}

            for col in df_pivot:
                cols[col] = df_pivot[col].values.tolist()

            rows = {}
            rows['metadata'] = {}

            metadata_row = ["end", "start", "index"]

            for row in df_pivot.index.names:
                if row in metadata_row:
                    rows[row] = df_pivot.index.get_level_values(row).values.tolist()
                else:
                    rows['metadata'][row] = df_pivot.index.get_level_values(row).values.tolist()

            result = {"cols": cols, "rows": rows, "globalStartIndex": (min(rows['start']))}

        else:
            cols = {}

            samples = eval(in_params_samples)

            for sa in samples:
                cols[sa] = []

            rows = { "end": [], "start": [], "index": [], "metadata": {} }
            result = {"cols": cols, "rows": rows, "globalStartIndex": None}
    except:
        error_info = sys.exc_info()
        error = str(error_info[0]) + " " + str(error_info[1]) + " " + str(error_info[2])
        response_status = 500

    return result, error, response_status

