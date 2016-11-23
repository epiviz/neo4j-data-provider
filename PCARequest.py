import utils
import pandas
from sklearn.decomposition import PCA

def get_data(in_params_selectedLevels, in_params_samples):

    tick_samples = in_params_samples.replace("\"", "\'")

    # get the min selected Level if aggregated at multiple levels
    minSelectedLevel = 6
    for level in in_params_selectedLevels.keys():
        if in_params_selectedLevels[level] == 2 and int(level) < minSelectedLevel:
            minSelectedLevel = int(level)

    qryStr = "MATCH (f:Feature)-[:LEAF_OF]->()<-[v:VALUE]-(s:Sample) WHERE (f.depth=" + str(minSelectedLevel) + ") AND s.id IN " + tick_samples + " with distinct f, s, SUM(v.val) as agg RETURN distinct agg, s.id, f.label as label, f.leafIndex as index, f.end as end, f.start as start, f.id as id, f.lineage as lineage, f.lineageLabel as lineageLabel, f.order as order"


    rq_res = utils.cypher_call(qryStr)
    df = utils.process_result(rq_res)

    #print(df)

    forPCAdf = df[["agg", "s.id", "label"]]

    forPCAmat = pandas.pivot_table(df, index=["label"], columns="s.id", values="agg", fill_value=0)
    
    #print(forPCAmat)
    pca = PCA(n_components = 2)
    pca.fit(forPCAmat)
    #print(pca.components_)
    #print(pca.explained_variance_ratio_)

    cols = {}
    cols['PC1'] = pca.components_[0]
    #cols['pc1_variance_explained'] = pca.explained_variance_ratio_[0]
    cols['PC2']= pca.components_[1]
    #cols['pc2_variance_explained'] = pca.explained_variance_ratio_[1]

    count = 0

    vals = []

    qryStr2 = "MATCH (s:Sample) WHERE s.id IN " + tick_samples + " RETURN s"

    rq_res2 = utils.cypher_call(qryStr2)
    df2 = utils.process_result_graph(rq_res2)
    #print(df2)
    vals = []

    for index, row in df2.iterrows():
        temp = {}
        #print(index)
        #print(row)
        #print(row.keys())
        #print(row.keys().values)
        for key in row.keys().values:
            temp[key] = row[key]
        temp['PC1'] = cols['PC1'][index]
        temp['PC2'] = cols['PC2'][index]
        #temp['pc1_variance_explained'] = cols['pc1_variance_explained']
        #temp['pc2_variance_explained'] = cols['pc2_variance_explained']
        #print(temp)
        temp['sample_id'] = temp['id']
        del temp['id']
        vals.append(temp)

    # for col in forPCAmat:
    #     row = {}
    #     row['pca1'] = cols['pca1'][count]
    #     row['pca2'] = cols['pca2'][count]
    #     row['sample_id'] = col
    #     vals.append(row)
    #     count = count+1

    #print(vals)

    resRowsCols = {"data": vals}
    variance_explained = pca.explained_variance_ratio_
    variance_explained[0] = round(variance_explained[0]*100.0, 2)
    variance_explained[1] = round(variance_explained[1]*100.0, 2)
    resRowsCols['pca_variance_explained'] = variance_explained

    #print resRowsCols

    return resRowsCols
